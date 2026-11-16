"""
SAIV Face Recognition & Risk Service - Module 3

This is the skeleton implementation for the Face Recognition module.
Students must implement face enrollment, verification, liveness detection,
and risk scoring.

Privacy Requirements:
- NO raw face images should be stored
- Process images in-memory only
- Store only SHA-256 hashes of face embeddings

Recommended Libraries:
- MediaPipe: Face detection and 468-landmark face mesh
- OpenCV: Image processing
- Pillow: Image loading from base64
- NumPy: Numerical operations
"""
from fastapi import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, AliasChoices, Field
from typing import Optional, Dict, List, Any, Literal
import numpy as np
import io
import ipaddress
import json
import logging
import math
from pathlib import Path
from PIL import Image, UnidentifiedImageError
import base64
import binascii
import mediapipe as mp
import hashlib
import re
import face_recognition
import cv2
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

logger = logging.getLogger("saiv.face")

app = FastAPI(
    title="SAIV Face Recognition Service",
    description="Face enrollment, verification, liveness detection, and risk scoring service",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mp_face_detection = mp.solutions.face_detection
mp_face_mesh = mp.solutions.face_mesh

# MediaPipe Face Mesh landmark indices (fixed by model topology)
NOSE_TIP = 1
LEFT_EYE_OUTER = 33
RIGHT_EYE_OUTER = 263
LEFT_MOUTH = 61
RIGHT_MOUTH = 291
CHIN = 152
FOREHEAD = 10
LEFT_CHEEK = 234
RIGHT_CHEEK = 454

# 6-point EAR sets per eye
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]

# Localised simhash constants
_SIMHASH_BITS = 256
_SIMHASH_SEED = 42

# Verification constants
MATCH_THRESHOLD =0.7
_HASH_HEX_LEN = _SIMHASH_BITS // 4
_HASH_RE = re.compile(rf"[0-9a-f]{{{_HASH_HEX_LEN}}}")

# average embedding of typical faces, calculated by compute_center.py offline
# dlib embedding
_EMBEDDING_DIM = 128            # dlib ResNet face descriptor size
_ENROLL_JITTERS = 5             # re-sampled crops averaged at enrollment (once per user)
_VERIFY_JITTERS = 1             # keep verification fast
_MIN_FACE_PX = 40               # smaller crops give unreliable embeddings

# Liveness
LIVENESS_THRESHOLD = 0.60
_SPOOF_CAP = 0.30               # score ceiling when a hard spoof indicator fires
_FAILED_CHALLENGE_CAP = 0.50    # ceiling when a supplied frame sequence fails its challenge
_MAX_FRAMES = 10
_LIVENESS_WEIGHTS = {
    "detection": 0.20,
    "quality": 0.15,
    "mesh": 0.10,
    "depth": 0.15,
    "texture": 0.30,
    "challenge": 0.10,
}
_DEPTH_SCORES = {"good": 1.0, "moderate": 0.6, "poor": 0.1}
# Texture calibration (face crop resized to 256 px wide). Measured on real photos
# vs blurred / grayscale / screen-recaptured versions of the same photos:
_SHARPNESS_FAIL = 15.0          # Laplacian variance; real faces 150-660, blurred 3.6
_SHARPNESS_GOOD = 80.0
_SATURATION_FAIL = 8.0          # mean HSV saturation; real 90-125, grayscale print 0
_CONTRAST_FAIL = 10.0           # grey-level std; uniform/flat images
_MOIRE_SOFT = 20.0              # FFT peak / radial median; real <= 18, screen 21-154
_MOIRE_FAIL = 40.0
_LANDMARKS_IN_FRAME_MIN = 0.95
# Challenge calibration (single-frame EAR is useless: open eyes measured 0.12-0.28,
# so blink is judged relative to the person's own open-eye EAR across frames)
_BLINK_CLOSED_RATIO = 0.70      # min EAR must drop below 70% of the open-eye EAR
_BLINK_REOPEN_RATIO = 0.85      # and eyes must be open (>=85%) before and after
_HEAD_TURN_YAW = 0.20           # |yaw| for a turned head in one frame
_HEAD_TURN_RANGE = 0.30         # yaw change across a sequence
_STATIC_FRAME_DIFF = 1.0        # mean abs pixel diff below this = identical frames
_SAME_PERSON_DISTANCE = 0.6     # dlib euclidean distance between frames

# Risk assessment
RISK_THRESHOLD = 0.50
_MISSING_SIGNAL_RISK = 0.5      # absent evidence is neither trusted nor damning
# A single near-certain red flag (failed nonce signature, impossible GPS,
# loopback IP, near-zero liveness) must not be averaged away by good face
# scores: it floors the total at CRITICAL.
_CRITICAL_SIGNAL_RISK = 0.9
_CRITICAL_FLOOR = 0.7
_RISK_WEIGHTS = {
    "liveness": 0.25,
    "face_match": 0.25,
    "device": 0.20,
    "network": 0.15,
    "geolocation": 0.15,
}

# \b so "tor" doesn't match "Editor"/"Navigator"; "-" counts as a boundary ("vpn-client")
_VPN_UA_RE = re.compile(
    r"\b(vpn|tor|torbrowser|proxy|openvpn|wireguard|nordvpn|expressvpn|protonvpn|"
    r"surfshark|tunnelbear|psiphon|hola|ultrasurf)\b",
    re.IGNORECASE,
)
_AUTOMATION_UA_RE = re.compile(
    r"(headlesschrome|phantomjs|selenium|webdriver|puppeteer|playwright|"
    r"python-requests|python-urllib|aiohttp|httpx|go-http-client|curl/|wget/|scrapy|okhttp)",
    re.IGNORECASE,
)
# Hook for known anonymiser ranges (Tor exit nodes, VPN/datacenter CIDRs).
# Populate from a vetted, dated list; wrong ranges here flag honest students.
_ANONYMISER_NETWORKS: List[ipaddress._BaseNetwork] = []
_CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")

_SUPPORTED_EC_CURVES = (ec.SECP256R1, ec.SECP384R1, ec.SECP521R1)
_JWK_CURVES = {"P-256": ec.SECP256R1, "P-384": ec.SECP384R1, "P-521": ec.SECP521R1}

# for prometheus
FACE_REQUESTS = Counter("face_requests_total", "Face service calls", ["endpoint", "outcome"])
FACE_LATENCY = Histogram("face_request_seconds", "Face service latency", ["endpoint"])



def _load_embedding_center() -> np.ndarray:
    """
    Mean dlib embedding over a diverse set of faces, produced offline by
    compute_center.py. Centering makes the SimHash hyperplanes split the region
    where faces actually live, pushing unrelated faces towards score 0.
    Falls back to the origin (still works, smaller margin) if the file is missing.
    """
    path = Path(__file__).with_name("embedding_center.npy")
    if path.exists():
        center = np.load(path)
        if center.shape == (_EMBEDDING_DIM,):
            return center.astype(np.float64)
        logger.warning("embedding_center.npy has shape %s, expected (%d,); ignoring",
                       center.shape, _EMBEDDING_DIM)
    else:
        logger.warning("embedding_center.npy not found; using uncentered SimHash")
    return np.zeros(_EMBEDDING_DIM)


_EMBEDDING_CENTER = _load_embedding_center()

# Raw SimHash similarity (1 - 2d/bits) at which two faces count as the same
# person. Calibrated on LFW (150 same-person pairs, 3000 different-person
# pairs) with the centred embedding: raw 0.32 gives <=1% false accepts and
# 5.3% false rejects. The calibration only holds for the centre it was measured
# with, so without a centre the raw score is used against 0.70 unchanged.
# Re-run calibrate_threshold.py whenever embedding_center.npy changes.
_CALIBRATED_RAW_THRESHOLD = 0.32
_RAW_MATCH_THRESHOLD = (
    _CALIBRATED_RAW_THRESHOLD if _EMBEDDING_CENTER.any() else MATCH_THRESHOLD
)

# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class FaceEnrollRequest(BaseModel):
    """Request model for face enrollment."""
    user_id: str
    image: str  # Base64 encoded image
    camera_consent: bool = False


class FaceEnrollResponse(BaseModel):
    """Response model for face enrollment."""
    enrollment_successful: bool
    face_template_hash: str  # 64-char SHA-256 hex string
    quality_score: float  # 0.0 to 1.0
    details: Dict[str, Any]


class FaceVerifyRequest(BaseModel):
    """Request model for face verification."""
    image: str  # Base64 encoded image
    reference_template_hash: str = Field(
        validation_alias=AliasChoices("reference_template_hash", "reference_hash")
    )



class FaceVerifyResponse(BaseModel):
    """Response model for face verification."""
    match_passed: bool
    match_score: float  # 0.0 to 1.0
    match_threshold: float  # Default: 0.70
    face_detected: bool
    current_template_hash: str


class LivenessRequest(BaseModel):
    """Request model for liveness check."""
    challenge_response: str  # Base64 encoded image (primary frame)
    challenge_type: Literal["blink", "head_turn", "passive"] = "blink"
    # Optional ordered capture of the challenge (e.g. 5-10 frames over ~2 s).
    # When supplied, blink/head_turn are actually verified across frames.
    frames: Optional[List[str]] = Field(None, max_length=_MAX_FRAMES)


class LivenessResponse(BaseModel):
    """Response model for liveness check."""
    liveness_passed: bool
    liveness_score: float  # 0.0 to 1.0
    liveness_threshold: float  # Default: 0.60
    face_embedding_hash: str
    details: Dict[str, Any]


class GeolocationData(BaseModel):
    """Geolocation data for risk assessment."""
    latitude: float
    longitude: float
    accuracy: float


class RiskAssessRequest(BaseModel):
    """Request model for risk assessment."""
    # Scores outside [0, 1] (or NaN) are malformed input -> 422
    liveness_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    face_match_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    device_signature: Optional[str] = Field(None, max_length=4096)
    device_public_key: Optional[str] = Field(None, max_length=8192)
    ip_address: Optional[str] = Field(None, max_length=64)
    user_agent: Optional[str] = Field(None, max_length=1024)
    geolocation: Optional[GeolocationData] = None
    # Optional server-issued nonce the device signed. When present together with
    # key + signature, the signature is verified cryptographically (anti-replay).
    challenge_nonce: Optional[str] = Field(None, max_length=1024)


class RiskAssessResponse(BaseModel):
    """Response model for risk assessment."""
    risk_score: float  # 0.0 to 1.0
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    pass_threshold: bool
    risk_threshold: float  # Default: 0.50
    signal_breakdown: Dict[str, float]
    signals: Dict[str, float]
    recommendations: List[str]


# =============================================================================
# HEALTH & ROOT ENDPOINTS
# =============================================================================
@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "face-recognition", "version": "1.0.0"}


@app.get("/")
async def root():
    """List available endpoints."""
    return {
        "service": "SAIV Face Recognition & Risk Service",
        "version": "1.0.0",
        "endpoints": {
            "/health": "GET - Health check",
            "/face/enroll": "POST - Enroll a face for verification",
            "/face/verify": "POST - Verify a face against enrolled template",
            "/face/match": "POST - Legacy face matching (use /face/verify)",
            "/liveness/check": "POST - Perform liveness detection",
            "/risk/assess": "POST - Multi-signal risk assessment",
        },
    }


# =============================================================================
# FACE ENROLLMENT ENDPOINT (REQUIRED - 4 points in public tests)
# =============================================================================

@app.post("/face/enroll", response_model=FaceEnrollResponse, status_code=201)
def enroll_face(request: FaceEnrollRequest):
    """Enroll a user's face: detect -> dlib embedding -> SimHash template."""
    if not request.camera_consent:
        raise HTTPException(status_code=400, detail="Camera consent required for enrollment")

    try:
        image_numpy_array = decode_base64_image(request.image)
    except ImageDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}") from None

    try:
        face_results = detect_face(image_numpy_array)
        if not face_results.detections:
            raise HTTPException(status_code=400, detail="No face detected")
        detection = face_results.detections[0]

        try:
            embedding = extract_face_embedding(
                image_numpy_array, detection, num_jitters=_ENROLL_JITTERS
            )
        except FaceEmbeddingError as e:
            raise HTTPException(status_code=400, detail=f"Face not usable for enrollment: {e}") from None

        template_hash = generate_face_hash(embedding)
        quality_score, quality_details = calculate_quality_score(detection, image_numpy_array.shape)
        del embedding
    finally:
        # Ephemeral processing (privacy requirement #3).
        del image_numpy_array

    return FaceEnrollResponse(
        enrollment_successful=quality_score >= 0.5,
        face_template_hash=template_hash,
        quality_score=quality_score,
        details=quality_details,
    )

# =============================================================================
# FACE VERIFICATION ENDPOINT (REQUIRED - 4 points in public tests)
# =============================================================================

@app.post("/face/verify", response_model=FaceVerifyResponse)
def verify_face(request: FaceVerifyRequest):
    """Verify a face against an enrolled SimHash template."""
    reference_hash = request.reference_template_hash.strip().lower()
    if not _HASH_RE.fullmatch(reference_hash):
        raise HTTPException(
            status_code=400,
            detail=f"reference_template_hash must be a {_HASH_HEX_LEN}-character hex string",
        )

    # Bad input (not a decodable image) -> 400.
    try:
        image_numpy_array = decode_base64_image(request.image)
    except ImageDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}") from None

    # Valid image, but possibly no usable face -> 200 with match_passed=False.
    try:
        face_results = detect_face(image_numpy_array)
        if not face_results.detections:
            return _unmatched(face_detected=False)

        try:
            embedding = extract_face_embedding(
                image_numpy_array, face_results.detections[0], num_jitters=_VERIFY_JITTERS
            )
        except FaceEmbeddingError:
            # Face found but couldn't be encoded: honest about detection,
            # but nothing to compare.
            return _unmatched(face_detected=True)

        current_hash = generate_face_hash(embedding)
        del embedding
    finally:
        del image_numpy_array

    match_score = round(compute_match_score(current_hash, reference_hash), 4)

    return FaceVerifyResponse(
        match_passed=match_score >= MATCH_THRESHOLD,
        match_score=match_score,
        match_threshold=MATCH_THRESHOLD,
        face_detected=True,
        current_template_hash=current_hash,
    )


@app.post("/face/match")
def match_face(request: FaceVerifyRequest):
    """Legacy face matching endpoint. Redirects to /face/verify."""
    return verify_face(request)


# =============================================================================
# LIVENESS DETECTION ENDPOINT (REQUIRED - partial; BONUS for advanced)
# =============================================================================

@app.post("/liveness/check", response_model=LivenessResponse)
def check_liveness(request: LivenessRequest):
    """
    Perform liveness detection on submitted image.

    TODO: Implement the following:
    1. Decode base64 image to numpy array
    2. Detect face using MediaPipe FaceDetection
    3. If no face detected, return with liveness_passed=False
    4. Analyze face for liveness signals:

    REQUIRED (for partial credit):
    - Basic face detection confidence
    - Image quality assessment
    - Face size validation

    BONUS (for extra credit - see API-SPECIFICATION.md):
    - MediaPipe Face Mesh 3D analysis (468 landmarks)
    - Depth cue analysis (nose_tip_z coordinate)
    - Face mesh completeness check
    - Challenge-response detection (blink, head movement)

    Challenge Types:
    - "passive": No user action required (depth/texture analysis)
    - "blink": Detect eye blink (compare eye aspect ratios)
    - "head_turn": Detect head rotation (face mesh landmarks)

    5. Calculate liveness_score (0.0 to 1.0)
    6. liveness_passed = (liveness_score >= 0.60)
    7. Generate face embedding hash

    Depth Analysis Hints (BONUS):
    - Use MediaPipe FaceMesh to get 3D landmarks
    - nose_tip_z (landmark 1, z-coordinate) indicates depth
    - Real faces: |nose_tip_z| > 0.03 (significant depth)
    - Flat images: |nose_tip_z| < 0.01 (minimal depth)
    """
    try:
        image = decode_base64_image(request.challenge_response)
        frame_images = [decode_base64_image(f) for f in request.frames] if request.frames else []
    except ImageDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}") from None

    try:
        primary = _analyze_liveness_frame(image, want_embedding=True)
        if primary is None:
            return _liveness_failed(request.challenge_type, "no face detected")

        spoof = list(primary["spoof_indicators"])
        challenge_score, challenge_details = _evaluate_challenge(
            request.challenge_type, primary, frame_images
        )
        spoof.extend(challenge_details.pop("spoof_indicators", []))

        components = {
            "detection": primary["detection_score"],
            "quality": primary["quality_score"],
            "mesh": primary["mesh_score"],
            "depth": _DEPTH_SCORES[primary["depth_quality"]],
            "texture": primary["texture_score"],
            "challenge": challenge_score,
        }
        score = sum(_LIVENESS_WEIGHTS[k] * v for k, v in components.items())
        if spoof:
            score = min(score, _SPOOF_CAP)
        if challenge_details["challenge_verified"] and not challenge_details["challenge_passed"]:
            score = min(score, _FAILED_CHALLENGE_CAP)
        score = round(min(1.0, max(0.0, score)), 4)

        face_hash = generate_face_hash(primary["embedding"]) if primary["embedding"] is not None else ""
    finally:
        # Ephemeral processing (privacy requirement #3).
        del image, frame_images

    details = {
        "face_detected": True,
        "challenge_type": request.challenge_type,
        "face_mesh_complete": primary["face_mesh_complete"],
        "landmark_count": primary["landmark_count"],
        "landmarks_in_frame": primary["landmarks_in_frame"],
        "nose_tip_z": primary["nose_tip_z"],
        "depth_quality": primary["depth_quality"],
        "detection_confidence": primary["detection_confidence"],
        "quality_score": primary["quality_score"],
        "texture": primary["texture"],
        **challenge_details,
        "spoof_indicators": spoof,
        "component_scores": {k: round(v, 4) for k, v in components.items()},
    }
    return LivenessResponse(
        liveness_passed=score >= LIVENESS_THRESHOLD,
        liveness_score=score,
        liveness_threshold=LIVENESS_THRESHOLD,
        face_embedding_hash=face_hash,
        details=details,
    )


# =============================================================================
# RISK ASSESSMENT ENDPOINT (REQUIRED - 3 points in public tests)
# =============================================================================

@app.post("/risk/assess", response_model=RiskAssessResponse)
def assess_risk(request: RiskAssessRequest):
    """
    Perform multi-signal risk assessment.

    TODO: Implement the following:
    1. Collect all available signals from request
    2. Calculate individual signal scores (0.0 = safe, 1.0 = risky)
    3. Apply weighted fusion:
       - Liveness: 25%
       - Face match: 25%
       - Device attestation: 20%
       - Network/VPN: 15%
       - Geolocation: 15%
    4. Calculate combined risk_score
    5. Determine risk_level:
       - LOW: risk_score < 0.3
       - MEDIUM: 0.3 <= risk_score < 0.5
       - HIGH: 0.5 <= risk_score < 0.7
       - CRITICAL: risk_score >= 0.7
    6. pass_threshold = (risk_score < 0.50)
    7. Generate recommendations for low-scoring signals

    Signal Analysis:
    - Liveness: Invert score (low liveness = high risk)
    - Face match: Invert score (low match = high risk)
    - Device: Check signature validity, public key format
    - Network: Detect VPN/proxy (private IPs, Tor exit nodes)
    - Geolocation: Check accuracy, validate coordinates

    VPN/Proxy Detection Hints:
    - Private IP ranges: 10.x.x.x, 172.16-31.x.x, 192.168.x.x
    - Check user_agent for VPN indicators
    - High geolocation accuracy (< 10m) might be spoofed
    - Very low accuracy (> 5000m) indicates issues
    """
        # Each assessor returns (risk in [0,1] or None if the signal is absent, reasons)
    assessed = {
        "liveness": _assess_inverted_score(request.liveness_score, "Liveness"),
        "face_match": _assess_inverted_score(request.face_match_score, "Face match"),
        "device": _assess_device(
            request.device_signature, request.device_public_key, request.challenge_nonce
        ),
        "network": _assess_network(request.ip_address, request.user_agent),
        "geolocation": _assess_geolocation(request.geolocation),
    }

    breakdown: Dict[str, float] = {}
    recommendations: List[str] = []
    for name, (risk, reasons) in assessed.items():
        if risk is None:
            risk = _MISSING_SIGNAL_RISK
            recommendations.append(f"{name}: signal not provided; collect it before trusting this check-in")
        elif risk >= 0.5:
            recommendations.extend(f"{name}: {r}" for r in reasons)
        breakdown[name] = round(float(risk), 4)

    risk_score = sum(_RISK_WEIGHTS[name] * breakdown[name] for name in _RISK_WEIGHTS)

    critical = [name for name, r in breakdown.items() if r >= _CRITICAL_SIGNAL_RISK]
    if critical:
        risk_score = max(risk_score, _CRITICAL_FLOOR)
        recommendations.insert(
            0, f"Critical signal(s) {', '.join(critical)}: block check-in and flag for instructor review"
        )
    risk_score = round(min(1.0, max(0.0, risk_score)), 4)

    return RiskAssessResponse(
        risk_score=risk_score,
        risk_level=_risk_level(risk_score),
        pass_threshold=risk_score < RISK_THRESHOLD,
        risk_threshold=RISK_THRESHOLD,
        signal_breakdown=breakdown,
        signals=dict(breakdown),
        recommendations=recommendations,
    )


# =============================================================================
# HELPER FUNCTIONS (Implement these to support your endpoints)
# =============================================================================

class ImageDecodeError(Exception):
    """raise when there is an error decoding image into np array"""
    pass
class FaceEmbeddingError(Exception):
    """Raised when a detected face can't be turned into an identity embedding."""
    pass
def decode_base64_image(base64_string: str):
    """
    Decode a base64 encoded image to a numpy array.

    TODO: Implement using:
    - base64.b64decode()
    - PIL.Image.open(BytesIO(...))
    - numpy.array()

    Handle errors gracefully (invalid base64, corrupt image, etc.)
    """
    if not base64_string or not isinstance(base64_string, str):
        raise ImageDecodeError("Input must be non-empty string")
    
    #extract out actual string
    if base64_string.startswith('data:'):
        try:
            base64_string = base64_string.split(',',1)[1]
        except IndexError:
            raise ImageDecodeError("Malformed data URL: missing comma separator")


    #b64 decode string into bytes, then open with PIL
    try:
        img_bytes = base64.b64decode(base64_string)
    except (binascii.Error, ValueError) as e:
        raise ImageDecodeError(f"Invalid base64 encoding: {e}") from e

    if not img_bytes:
        raise ImageDecodeError("Decoded base64 produced empty bytes")

    try:
        img = Image.open(io.BytesIO(img_bytes))
        img.load() #force full decode now
    except UnidentifiedImageError as e:
        raise ImageDecodeError("Bytes dont represent valid image format")
    except OSError as e:
        raise ImageDecodeError(f"Corrupt or truncated image data: {e}")

    try:
        img = img.convert("RGB")
        numpy_array = np.array(img)
        if numpy_array.dtype != np.uint8:
            numpy_array = numpy_array.astype(np.uint8)
        return numpy_array
    except Exception as e:
        raise ImageDecodeError(f"Failed to convert image to array: {e}") from e


def calculate_quality_score(detection, image_shape):
    h,w = image_shape[:2]

    confidence_score = detection.score[0]

    min_dimension = min(h,w)
    MIN_ACCEPTABLE_RES = 200
    GOOD_RES = 480

    if min_dimension >= GOOD_RES:
        resolution_score = 1.0
    elif min_dimension <= MIN_ACCEPTABLE_RES:
        resolution_score = min_dimension / MIN_ACCEPTABLE_RES * 0.5
    else:
        resolution_score = 0.5 + 0.5 * (min_dimension - MIN_ACCEPTABLE_RES) / (GOOD_RES - MIN_ACCEPTABLE_RES)
    bbox = detection.location_data.relative_bounding_box
    face_area_ratio = bbox.width * bbox.height

    IDEAL_MIN = 0.05
    IDEAL_MAX = 0.65

    if IDEAL_MIN <= face_area_ratio <= IDEAL_MAX:
        size_score = 1.0
    elif face_area_ratio < IDEAL_MIN:
        size_score = max(0.0, face_area_ratio / IDEAL_MIN)
    else:
        size_score = max(0.0, 1.0 - (face_area_ratio - IDEAL_MAX) / (1.0 - IDEAL_MAX))

    quality_score = (
        0.5 * confidence_score + 0.25 * resolution_score + 0.25 * size_score
    )

    quality_score = round(min(1.0, max(0.0, quality_score)), 4)

    details = {
        "confidence_score": round(confidence_score, 4),
        "resolution_score": round(resolution_score, 4),
        "size_score": round(size_score, 4),
        "image_resolution": f"{w}x{h}",
        "face_area_ratio": round(face_area_ratio, 4)
    }
    return quality_score, details

def detect_face(image_array):
    """
    Detect faces in an image using MediaPipe.

    TODO: Implement using:
    - mediapipe.solutions.face_detection.FaceDetection
    - Return detection results with confidence scores

    Consider setting min_detection_confidence=0.5
    """
    if image_array is None or image_array.size == 0:
        raise ImageDecodeError("Cannot detect face: empty image array")
    try:
        with mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.7
        ) as face_detection:
            results = face_detection.process(image_array)
            
    except Exception as e:
        raise ImageDecodeError(f"Face detection failed: {e}") from e
    return results
        
def _detection_to_dlib_box(detection, image_shape) -> tuple:
    """
    Convert a MediaPipe relative bbox to dlib's (top, right, bottom, left) in
    pixels, clamped to the image. Passing this to face_recognition skips dlib's
    own (slow) HOG detector and guarantees we embed the same face MediaPipe
    scored for quality.
    """
    h, w = image_shape[:2]
    bbox = detection.location_data.relative_bounding_box
    left = max(0, int(round(bbox.xmin * w)))
    top = max(0, int(round(bbox.ymin * h)))
    right = min(w, int(round((bbox.xmin + bbox.width) * w)))
    bottom = min(h, int(round((bbox.ymin + bbox.height) * h)))
    return top, right, bottom, left


def extract_face_embedding(image_array, detection, num_jitters: int = 1) -> np.ndarray:
    """
    128-d identity embedding from dlib's ResNet face descriptor.

    dlib aligns the face internally (5-point landmarks) before encoding, so
    pose/scale normalisation is handled for us. num_jitters > 1 averages
    embeddings over slightly perturbed crops: steadier template, ~linear cost.
    """
    top, right, bottom, left = _detection_to_dlib_box(detection, image_array.shape)
    if (right - left) < _MIN_FACE_PX or (bottom - top) < _MIN_FACE_PX:
        raise FaceEmbeddingError(
            f"face too small ({right - left}x{bottom - top}px, need {_MIN_FACE_PX}px)"
        )

    encodings = face_recognition.face_encodings(
        image_array,
        known_face_locations=[(top, right, bottom, left)],
        num_jitters=num_jitters,
    )
    if not encodings:
        raise FaceEmbeddingError("could not compute face encoding")

    return np.asarray(encodings[0], dtype=np.float64)


def _get_simhash_planes(dim: int, num_bits: int = _SIMHASH_BITS) -> np.ndarray:
    """
    Deterministic random hyperplanes for SimHash projection.
    Cached at module load so it's computed once, not per-request.
    """
    rng = np.random.default_rng(_SIMHASH_SEED)
    return rng.normal(size=(num_bits, dim))

# computed once at import time, reused across all requests
_SIMHASH_PLANES = _get_simhash_planes(dim=_EMBEDDING_DIM)

def generate_face_hash(embedding) -> str:
    """
    SimHash of the (centered) embedding: similar embeddings -> similar hashes
    (low Hamming distance). 256 bits -> 64 hex chars.
    """
    if embedding is None or embedding.size == 0:
        raise FaceEmbeddingError("Cannot hash empty embedding")
    if embedding.shape[0] != _SIMHASH_PLANES.shape[1]:
        raise FaceEmbeddingError(
            f"Embedding dimension {embedding.shape[0]} doesn't match "
            f"SimHash planes dimension {_SIMHASH_PLANES.shape[1]}"
        )
    projections = _SIMHASH_PLANES @ (embedding - _EMBEDDING_CENTER)  # (256,)
    bits = (projections >= 0).astype(np.uint8)

    bit_string = ''.join(str(b) for b in bits)
    return format(int(bit_string, 2), f'0{_HASH_HEX_LEN}x')

def analyze_face_mesh(image_array):
    """
    Analyze face using MediaPipe Face Mesh (BONUS).

    TODO: Implement using:
    - mediapipe.solutions.face_mesh.FaceMesh
    - Extract 468 landmarks
    - Calculate depth from nose_tip_z (landmark index 1)
    - Check mesh completeness

    Return dict with:
    - face_mesh_complete: bool
    - landmark_count: int
    - nose_tip_z: float
    - depth_quality: "good" | "moderate" | "poor"
    """
    with mp_face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=False,
        min_detection_confidence=0.7
    ) as face_mesh:
        results = face_mesh.process(image_array)

    if not results.multi_face_landmarks:
        return {
            "face_mesh_complete": False,
            "landmark_count": 0,
            "nose_tip_z": 0.0,
            "depth_quality": "poor",
            "landmarks": None,
        }

    landmarks = results.multi_face_landmarks[0].landmark
    landmark_count = len(landmarks)
    nose_tip_z = landmarks[NOSE_TIP].z

    abs_z = abs(nose_tip_z)
    if abs_z > 0.03:
        depth_quality = "good"
    elif abs_z > 0.01:
        depth_quality = "moderate"
    else:
        depth_quality = "poor"

    return {
        "face_mesh_complete": landmark_count == 468,
        "landmark_count": landmark_count,
        "nose_tip_z": nose_tip_z,
        "depth_quality": depth_quality,
        "landmarks": landmarks,
    }
        
def _eye_aspect_ratio(landmarks, eye_indices) -> float:
    points = np.array([[landmarks[i].x, landmarks[i].y] for i in eye_indices])
    vertical_1 = np.linalg.norm(points[1] - points[5])
    vertical_2 = np.linalg.norm(points[2] - points[4])
    horizontal = np.linalg.norm(points[0] - points[3])

    if horizontal < 1e-6:
        return 0.0

    return (vertical_1 + vertical_2) / (2.0 * horizontal)

def detect_blink(face_mesh_landmarks, ear_threshold: float=0.21):
    """
    Detect eye blink from face mesh landmarks (BONUS).

    TODO: Implement using:
    - Eye landmark indices (see MediaPipe docs)
    - Calculate Eye Aspect Ratio (EAR)
    - EAR < threshold indicates closed eye
    """
    if face_mesh_landmarks is None:
        return {"blink_detected": False, "left_ear": 0.0, "right_ear": 0.0, "avg_ear": 0.0}

    left_ear = _eye_aspect_ratio(face_mesh_landmarks, LEFT_EYE)
    right_ear = _eye_aspect_ratio(face_mesh_landmarks, RIGHT_EYE)
    avg_ear = (left_ear + right_ear) / 2.0

    return {
        "blink_detected": avg_ear < ear_threshold,
        "left_ear": left_ear,
        "right_ear": right_ear,
        "avg_ear": avg_ear,
    }


def detect_vpn_proxy(ip_address: str, user_agent: str) -> tuple:
    """
    Detect VPN/proxy usage.

    TODO: Check for:
    - Private IP ranges (10.x, 172.16-31.x, 192.168.x)
    - Localhost (127.x, ::1)
    - VPN keywords in user_agent
    - Known proxy headers (not available here, but could extend)

    Return (is_vpn: bool, confidence: float)
    """
    indicators = _vpn_indicators(ip_address, user_agent)
    confidence = max((c for c, _ in indicators), default=0.0)
    return confidence >= 0.5, confidence

def _vpn_indicators(ip_address: Optional[str], user_agent: Optional[str]) -> List[tuple]:
    """List of (confidence, reason) for VPN/proxy/anonymiser evidence."""
    found = []
    if ip_address:
        try:
            ip = ipaddress.ip_address(ip_address.strip())
        except ValueError:
            ip = None  # malformed IPs are scored by _assess_network
        if ip is not None:
            if ip.is_loopback or ip.is_unspecified:
                found.append((0.9, f"loopback/unspecified IP {ip}: request is not from a real client"))
            elif ip.is_private or ip.is_link_local:
                found.append((0.8, f"private IP {ip}: typical of VPN tunnels or proxies"))
            elif ip.is_reserved or ip.is_multicast:
                found.append((0.9, f"reserved/multicast IP {ip} is not a valid client address"))
            elif ip.version == 4 and ip in _CGNAT_NETWORK:
                found.append((0.4, f"carrier-grade NAT IP {ip}: shared, weak location evidence"))
            if any(ip in net for net in _ANONYMISER_NETWORKS):
                found.append((0.95, f"IP {ip} is in a known anonymiser range"))
    if user_agent and _VPN_UA_RE.search(user_agent):
        found.append((0.9, "user agent mentions a VPN/proxy/Tor client"))
    return found


# -----------------------------------------------------------------------------
# Risk assessment helpers. Each returns (risk or None if absent, [reasons]).
# -----------------------------------------------------------------------------

def _risk_level(score: float) -> str:
    if score < 0.3:
        return "LOW"
    if score < 0.5:
        return "MEDIUM"
    if score < 0.7:
        return "HIGH"
    return "CRITICAL"


def _assess_inverted_score(score: Optional[float], label: str) -> tuple:
    """Liveness / face match: high score = low risk."""
    if score is None:
        return None, []
    risk = 1.0 - score
    return risk, [f"{label} score {score:.2f} is low; retry the capture or escalate to manual review"]


def _assess_network(ip_address: Optional[str], user_agent: Optional[str]) -> tuple:
    if not ip_address and not user_agent:
        return None, []

    findings = list(_vpn_indicators(ip_address, user_agent))

    if not ip_address:
        findings.append((_MISSING_SIGNAL_RISK, "client IP not provided"))
    else:
        try:
            ipaddress.ip_address(ip_address.strip())
        except ValueError:
            findings.append((0.9, "malformed IP address"))

    if not user_agent or not user_agent.strip():
        findings.append((0.4, "user agent missing"))
    elif _AUTOMATION_UA_RE.search(user_agent):
        findings.append((0.8, "user agent indicates a script or headless browser, not the PWA"))
    elif len(user_agent.strip()) < 20:
        findings.append((0.2, "user agent is unusually minimal"))

    if not findings:
        return 0.0, []
    risk = max(c for c, _ in findings)
    return risk, [r for c, r in sorted(findings, reverse=True) if c >= 0.5]


def _coarse(value: float) -> bool:
    """True if the coordinate has <= 2 decimal places (~1 km precision)."""
    return math.isclose(value, round(value, 2), abs_tol=1e-9)


def _assess_geolocation(geo: Optional[GeolocationData]) -> tuple:
    if geo is None:
        return None, []

    lat, lon, acc = geo.latitude, geo.longitude, geo.accuracy
    if not all(math.isfinite(v) for v in (lat, lon, acc)):
        return 1.0, ["geolocation contains NaN/infinite values"]
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return 1.0, [f"coordinates ({lat}, {lon}) are outside valid ranges"]

    findings = []
    if abs(lat) < 1e-6 and abs(lon) < 1e-6:
        findings.append((0.9, "coordinates are (0, 0): default/placeholder location, likely spoofed"))
    if acc <= 0:
        findings.append((0.9, f"accuracy {acc} m is impossible for a real fix"))
    elif acc < 10:
        findings.append((0.6, f"accuracy {acc} m is suspiciously precise; possible mock location"))
    elif acc > 5000:
        findings.append((0.7, f"accuracy {acc} m is too coarse to place the student at the venue"))
    elif acc > 1000:
        findings.append((0.4, f"accuracy {acc} m is coarse"))
    if _coarse(lat) and _coarse(lon):
        findings.append((0.6, "coordinates have <= 2 decimal places; real GPS fixes are finer"))

    if not findings:
        return 0.0, []
    risk = max(c for c, _ in findings)
    return risk, [r for c, r in sorted(findings, reverse=True) if c >= 0.5]


def _b64_or_hex_decode(value: str) -> Optional[bytes]:
    """Decode base64, base64url (padding optional) or hex. None if none fit."""
    value = value.strip()
    if re.fullmatch(r"(?:[0-9a-fA-F]{2})+", value) and len(value) % 2 == 0 and len(value) >= 64:
        return bytes.fromhex(value)
    # Normalise base64url -> base64, restore padding, then decode strictly
    # (non-strict decoding silently drops invalid characters).
    normalised = value.replace("-", "+").replace("_", "/")
    normalised += "=" * (-len(normalised) % 4)
    try:
        out = base64.b64decode(normalised.encode("ascii"), validate=True)
    except (binascii.Error, ValueError, UnicodeEncodeError):
        return None
    return out or None


def _load_public_key(value: str):
    """Accept PEM, base64 SPKI/DER, or an EC JWK (WebCrypto exports). None if unparseable."""
    value = value.strip()
    try:
        if "BEGIN" in value:
            return serialization.load_pem_public_key(value.encode())
        if value.startswith("{"):
            jwk = json.loads(value)
            curve = _JWK_CURVES.get(jwk.get("crv"))
            if jwk.get("kty") != "EC" or curve is None:
                return None
            x = int.from_bytes(_b64_or_hex_decode(jwk["x"]) or b"", "big")
            y = int.from_bytes(_b64_or_hex_decode(jwk["y"]) or b"", "big")
            return ec.EllipticCurvePublicNumbers(x, y, curve()).public_key()
        der = _b64_or_hex_decode(value)
        return serialization.load_der_public_key(der) if der else None
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def _key_weakness(key) -> Optional[str]:
    if isinstance(key, rsa.RSAPublicKey):
        return None if key.key_size >= 2048 else f"RSA key is only {key.key_size} bits"
    if isinstance(key, ec.EllipticCurvePublicKey):
        return None if isinstance(key.curve, _SUPPORTED_EC_CURVES) else f"unsupported curve {key.curve.name}"
    if isinstance(key, ed25519.Ed25519PublicKey):
        return None
    return f"unsupported key type {type(key).__name__}"


def _verify_signature(key, signature: bytes, message: bytes) -> bool:
    try:
        if isinstance(key, ec.EllipticCurvePublicKey):
            size = (key.curve.key_size + 7) // 8
            if len(signature) == 2 * size:
                # WebCrypto emits raw r||s; cryptography expects DER
                r = int.from_bytes(signature[:size], "big")
                s_ = int.from_bytes(signature[size:], "big")
                signature = encode_dss_signature(r, s_)
            key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
        elif isinstance(key, rsa.RSAPublicKey):
            try:
                key.verify(signature, message, padding.PKCS1v15(), hashes.SHA256())
            except InvalidSignature:
                key.verify(signature, message,
                           padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
                           hashes.SHA256())
        elif isinstance(key, ed25519.Ed25519PublicKey):
            key.verify(signature, message)
        else:
            return False
        return True
    except (InvalidSignature, ValueError):
        return False


def _assess_device(signature: Optional[str], public_key: Optional[str],
                   nonce: Optional[str]) -> tuple:
    if not signature and not public_key:
        return None, []

    findings = []
    key = None
    if public_key:
        key = _load_public_key(public_key)
        if key is None:
            findings.append((0.8, "device public key could not be parsed"))
        else:
            weakness = _key_weakness(key)
            if weakness:
                findings.append((0.6, weakness))
    else:
        findings.append((0.6, "no device public key: device is not bound"))

    sig_bytes = None
    if signature:
        sig_bytes = _b64_or_hex_decode(signature)
        if sig_bytes is None or len(sig_bytes) < 32:
            findings.append((0.8, "device signature is malformed"))
            sig_bytes = None
    else:
        findings.append((0.6, "no device signature"))

    # Strongest evidence: an actual signature over a server-issued nonce.
    if nonce and key is not None and sig_bytes is not None:
        if _verify_signature(key, sig_bytes, nonce.encode("utf-8")):
            return 0.0, []
        return 1.0, ["device signature does not verify against the challenge nonce: "
                     "possible replay or impersonation"]

    if not findings:
        # Well-formed but unverified (no nonce supplied)
        return 0.1, []
    risk = max(c for c, _ in findings)
    return risk, [r for c, r in sorted(findings, reverse=True) if c >= 0.5]

# -----------------------------------------------------------------------------
# Liveness helpers
# -----------------------------------------------------------------------------

def _liveness_failed(challenge_type: str, reason: str) -> LivenessResponse:
    return LivenessResponse(
        liveness_passed=False,
        liveness_score=0.0,
        liveness_threshold=LIVENESS_THRESHOLD,
        face_embedding_hash="",
        details={
            "face_detected": False,
            "challenge_type": challenge_type,
            "face_mesh_complete": False,
            "landmark_count": 0,
            "nose_tip_z": 0.0,
            "depth_quality": "poor",
            "reason": reason,
        },
    )


def _face_crop(image_array, detection) -> np.ndarray:
    top, right, bottom, left = _detection_to_dlib_box(detection, image_array.shape)
    return image_array[top:bottom, left:right]


def _moire_ratio(gray: np.ndarray) -> float:
    """
    Strongest periodic peak in the face crop's spectrum relative to the median
    energy at the same frequency. Screens and halftone prints add sharp peaks
    (moire); real skin and JPEG compression don't.
    """
    g = gray.astype(np.float32) - gray.mean()
    g *= np.outer(np.hanning(g.shape[0]), np.hanning(g.shape[1]))
    spectrum = np.abs(np.fft.fftshift(np.fft.fft2(g)))
    h, w = spectrum.shape
    yy, xx = np.mgrid[-(h // 2):h - h // 2, -(w // 2):w - w // 2]
    radius = np.round(np.hypot(xx, yy)).astype(int)
    ratio = 0.0
    for r in range(20, min(h, w) // 2 - 18):
        ring = spectrum[radius == r]
        med = np.median(ring)
        if med > 0:
            ratio = max(ratio, float(ring.max() / med))
    return ratio


def _texture_analysis(crop: np.ndarray) -> tuple:
    """Returns (texture_score 0-1, details, spoof_indicators)."""
    resized = cv2.resize(crop, (256, 256))
    gray = cv2.cvtColor(resized, cv2.COLOR_RGB2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    contrast = float(gray.std())
    saturation = float(cv2.cvtColor(resized, cv2.COLOR_RGB2HSV)[..., 1].mean())
    moire = _moire_ratio(gray)

    spoof = []
    if sharpness < _SHARPNESS_FAIL:
        spoof.append("blurred_or_recaptured")
    if saturation < _SATURATION_FAIL:
        spoof.append("grayscale_image")
    if contrast < _CONTRAST_FAIL:
        spoof.append("flat_low_contrast")
    if moire >= _MOIRE_FAIL:
        spoof.append("screen_moire_pattern")

    sharp_score = float(np.clip((sharpness - _SHARPNESS_FAIL) / (_SHARPNESS_GOOD - _SHARPNESS_FAIL), 0, 1))
    moire_score = float(np.clip((_MOIRE_FAIL - moire) / (_MOIRE_FAIL - _MOIRE_SOFT), 0, 1))
    colour_score = float(np.clip(saturation / 40.0, 0, 1))
    score = min(sharp_score, moire_score, colour_score)

    details = {
        "sharpness": round(sharpness, 1),
        "saturation": round(saturation, 1),
        "contrast": round(contrast, 1),
        "moire_ratio": round(moire, 1),
    }
    return score, details, spoof


def _head_yaw(landmarks) -> float:
    """Signed yaw proxy in [-1, 1] from nose-to-cheek asymmetry (0 = frontal)."""
    nose, left, right = landmarks[NOSE_TIP].x, landmarks[LEFT_CHEEK].x, landmarks[RIGHT_CHEEK].x
    d_left, d_right = abs(nose - left), abs(right - nose)
    total = d_left + d_right
    return 0.0 if total < 1e-6 else (d_left - d_right) / total


def _analyze_liveness_frame(image_array, want_embedding: bool = False) -> Optional[dict]:
    """All single-frame liveness signals. None if no face is detected."""
    face_results = detect_face(image_array)
    if not face_results.detections:
        return None
    detection = face_results.detections[0]
    confidence = float(detection.score[0])
    quality, _ = calculate_quality_score(detection, image_array.shape)

    mesh = analyze_face_mesh(image_array)
    landmarks = mesh["landmarks"]
    spoof = []
    if landmarks is not None:
        pts = np.array([[lm.x, lm.y] for lm in landmarks])
        in_frame = float(np.mean((pts >= 0.0).all(axis=1) & (pts <= 1.0).all(axis=1)))
        ear = detect_blink(landmarks)["avg_ear"]
        yaw = _head_yaw(landmarks)
    else:
        in_frame, ear, yaw = 0.0, None, None
    mesh_complete = landmarks is not None and in_frame >= _LANDMARKS_IN_FRAME_MIN
    if not mesh_complete:
        spoof.append("incomplete_face")

    texture_score, texture, texture_spoof = _texture_analysis(_face_crop(image_array, detection))
    spoof.extend(texture_spoof)

    embedding = None
    if want_embedding:
        try:
            embedding = extract_face_embedding(image_array, detection, num_jitters=_VERIFY_JITTERS)
        except FaceEmbeddingError:
            spoof.append("face_too_small")

    return {
        "detection_confidence": round(confidence, 4),
        "detection_score": float(np.clip((confidence - 0.5) / 0.5, 0, 1)),
        "quality_score": quality,
        "face_mesh_complete": mesh_complete,
        "landmark_count": mesh["landmark_count"],
        "landmarks_in_frame": round(in_frame, 4),
        "mesh_score": 1.0 if mesh_complete else in_frame * 0.5,
        "nose_tip_z": round(float(mesh["nose_tip_z"]), 4),
        "depth_quality": mesh["depth_quality"],
        "texture_score": texture_score,
        "texture": texture,
        "ear": None if ear is None else round(float(ear), 4),
        "yaw": None if yaw is None else round(float(yaw), 4),
        "embedding": embedding,
        "spoof_indicators": spoof,
    }


def _blink_in_sequence(ears: List[float]) -> bool:
    """Open -> closed -> open, judged against this person's own open-eye EAR."""
    if len(ears) < 3:
        return False
    open_ear = max(ears)
    if open_ear <= 0:
        return False
    i = int(np.argmin(ears))
    closed = ears[i] < _BLINK_CLOSED_RATIO * open_ear
    open_before = any(e >= _BLINK_REOPEN_RATIO * open_ear for e in ears[:i])
    open_after = any(e >= _BLINK_REOPEN_RATIO * open_ear for e in ears[i + 1:])
    return closed and open_before and open_after


def _frames_are_static(frames: List[np.ndarray]) -> bool:
    """True if every frame is (near-)identical: one still image resubmitted."""
    small = [cv2.cvtColor(cv2.resize(f, (128, 128)), cv2.COLOR_RGB2GRAY).astype(np.float32) for f in frames]
    diffs = [float(np.mean(np.abs(a - b))) for a, b in zip(small, small[1:])]
    return bool(diffs) and max(diffs) < _STATIC_FRAME_DIFF


def _evaluate_challenge(challenge_type: str, primary: dict, frames: List[np.ndarray]) -> tuple:
    """
    Returns (challenge_score 0-1, details). With >= 3 frames the challenge is
    verified; with a single frame it is only weakly indicated (score 0.5 for
    blink, |yaw|-based for head_turn), never treated as proven.
    """
    details = {"frames_analyzed": 1 + len(frames), "challenge_verified": False,
               "challenge_passed": None, "spoof_indicators": []}

    if challenge_type == "passive":
        details["challenge_passed"] = True
        return 1.0, details

    if len(frames) < 3:
        details["challenge_note"] = "single frame: send 3+ frames in `frames` to verify the challenge"
        if challenge_type == "head_turn" and primary["yaw"] is not None:
            details["yaw"] = primary["yaw"]
            return float(np.clip(abs(primary["yaw"]) / _HEAD_TURN_YAW, 0, 1)), details
        details["ear"] = primary["ear"]
        return 0.5, details

    analyses = [_analyze_liveness_frame(f, want_embedding=True) for f in frames]
    details["challenge_verified"] = True

    if any(a is None or a["ear"] is None for a in analyses):
        details["challenge_passed"] = False
        details["spoof_indicators"].append("face_missing_in_sequence")
        return 0.0, details

    if _frames_are_static(frames):
        details["challenge_passed"] = False
        details["spoof_indicators"].append("static_frame_sequence")
        return 0.0, details

    ref = primary["embedding"]
    if ref is not None and any(
        a["embedding"] is not None and np.linalg.norm(a["embedding"] - ref) > _SAME_PERSON_DISTANCE
        for a in analyses
    ):
        details["challenge_passed"] = False
        details["spoof_indicators"].append("identity_changed_in_sequence")
        return 0.0, details

    if challenge_type == "blink":
        ears = [a["ear"] for a in analyses]
        details["ear_sequence"] = ears
        passed = _blink_in_sequence(ears)
    else:  # head_turn
        yaws = [a["yaw"] for a in analyses]
        details["yaw_sequence"] = yaws
        passed = (max(yaws) - min(yaws)) >= _HEAD_TURN_RANGE

    details["challenge_passed"] = passed
    return (1.0 if passed else 0.0), details

def hamming_distance_hex(hash1: str, hash2: str) -> int:
    """Number of differing bits between two equal-length hex strings."""
    return (int(hash1, 16) ^ int(hash2, 16)).bit_count()

def compute_match_score(current_hash: str, reference_hash: str,
                        total_bits: int = _SIMHASH_BITS) -> float:
    """
    Map SimHash Hamming distance to a calibrated 0-1 match score.

    Raw similarity: expected differing-bit fraction = angle / pi, so unrelated
    embeddings differ in ~half their bits; 1 - 2d/bits puts chance at 0 and
    identical at 1.

    Calibration: the raw decision point (_RAW_MATCH_THRESHOLD, measured on
    LFW) is mapped onto MATCH_THRESHOLD (0.70, fixed by the API spec) with a
    piecewise-linear, monotonic rescale. 0 stays 0, 1 stays 1, and
    match_passed = score >= 0.70 makes exactly the calibrated decision.
    """
    d = hamming_distance_hex(current_hash, reference_hash)
    raw = max(0.0, 1.0 - 2.0 * d / total_bits)
    t = _RAW_MATCH_THRESHOLD
    if raw >= t:
        return MATCH_THRESHOLD + (1.0 - MATCH_THRESHOLD) * (raw - t) / (1.0 - t)
    return MATCH_THRESHOLD * raw / t
 
 
def _unmatched(face_detected: bool, current_hash: str = "") -> FaceVerifyResponse:
    return FaceVerifyResponse(
        match_passed=False,
        match_score=0.0,
        match_threshold=MATCH_THRESHOLD,
        face_detected=face_detected,
        current_template_hash=current_hash,
    )


# =============================================================================
# PRIVACY REQUIREMENTS (IMPORTANT!)
# =============================================================================
"""
Your implementation MUST follow these privacy requirements:

1. NO RAW IMAGES STORED
   - Process images in-memory only
   - Do not write images to disk
   - Do not send images to external APIs

2. HASH-ONLY STORAGE
   - Store only SHA-256 hashes (64 hex characters)
   - Hashes are one-way - cannot reconstruct face
   - Different faces must produce different hashes

3. EPHEMERAL PROCESSING
   - Clear image data after processing
   - No caching of raw biometric data
   - Use Python's memory management (del, gc.collect)

4. CONSENT TRACKING
   - Require camera_consent=True for enrollment
   - Log consent in audit trail (backend responsibility)

5. RESPONSE HYGIENE
   - Never include base64 image data in responses
   - Only return hashes, scores, and metadata
"""
