"""
Local liveness tests for Module 3 (not part of the graded suite).

Runs against the live service over HTTP, so it tests the Docker container
exactly as other modules call it.

    export TEST_FACE_URL=http://localhost:8001     # default
    pytest tests/local/test_liveness.py -v

Needs the sample images (obama.jpg, obama2.jpg, biden.jpg). They're found by
searching upwards from this file for a `sample_images` folder, or set
SAMPLE_IMAGES_DIR explicitly.
"""
import base64
import io
import os
from pathlib import Path

import httpx
import numpy as np
import pytest
from PIL import Image, ImageFilter

BASE_URL = os.environ.get("TEST_FACE_URL", "http://localhost:8001")
THRESHOLD = 0.60
SPEC_DETAIL_KEYS = {"face_mesh_complete", "landmark_count", "nose_tip_z", "depth_quality", "challenge_type"}


# -----------------------------------------------------------------------------
# Fixtures and image helpers
# -----------------------------------------------------------------------------

def _find_sample_dir() -> Path:
    if os.environ.get("SAMPLE_IMAGES_DIR"):
        return Path(os.environ["SAMPLE_IMAGES_DIR"])
    for parent in Path(__file__).resolve().parents:
        if (parent / "sample_images" / "obama.jpg").exists():
            return parent / "sample_images"
    pytest.skip("sample_images folder with obama.jpg not found; set SAMPLE_IMAGES_DIR")


@pytest.fixture(scope="session")
def client():
    c = httpx.Client(base_url=BASE_URL, timeout=60)
    try:
        if c.get("/health").status_code != 200:
            pytest.skip(f"face service at {BASE_URL} is not healthy")
    except httpx.HTTPError:
        pytest.skip(f"face service not reachable at {BASE_URL}")
    yield c
    c.close()


@pytest.fixture(scope="session")
def img():
    d = _find_sample_dir()
    return {n: np.array(Image.open(d / f"{n}.jpg").convert("RGB")) for n in ("obama", "obama2", "biden")}


def b64(array: np.ndarray) -> str:
    buf = io.BytesIO()
    Image.fromarray(array).save(buf, "JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode()


def blurred(a):
    return np.array(Image.fromarray(a).filter(ImageFilter.GaussianBlur(6)))


def grayscale(a):
    return np.array(Image.fromarray(a).convert("L").convert("RGB"))


def screen_replay(a):
    """Simulated photo of a screen: resolution loss plus a moire interference pattern."""
    h, w = a.shape[:2]
    low = Image.fromarray(a).resize((w // 3, h // 3)).resize((w, h))
    yy, xx = np.mgrid[:h, :w]
    pattern = 18 * np.sin((xx * 0.8 + yy * 0.6) * 0.9)[..., None]
    return np.clip(np.array(low) + pattern, 0, 255).astype(np.uint8)


def with_noise(a, seed):
    """Same image with camera-like sensor noise, so frames aren't byte-identical."""
    noise = np.random.default_rng(seed).integers(-6, 7, a.shape)
    return np.clip(a.astype(int) + noise, 0, 255).astype(np.uint8)


def check(client, image, challenge="passive", frames=None):
    body = {"challenge_response": b64(image), "challenge_type": challenge}
    if frames is not None:
        body["frames"] = [b64(f) for f in frames]
    r = client.post("/liveness/check", json=body)
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:300]}"
    return r.json()


# -----------------------------------------------------------------------------
# Real faces pass, and the response follows the spec
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["obama", "obama2", "biden"])
@pytest.mark.parametrize("challenge", ["passive", "blink", "head_turn"])
def test_real_face_passes(client, img, name, challenge):
    d = check(client, img[name], challenge)
    assert d["liveness_passed"] is True, d["details"]
    assert d["liveness_score"] >= THRESHOLD
    assert d["details"]["spoof_indicators"] == []


def test_response_format(client, img):
    d = check(client, img["obama"], "blink")
    assert set(d) >= {"liveness_passed", "liveness_score", "liveness_threshold", "face_embedding_hash", "details"}
    assert 0 <= d["liveness_score"] <= 1
    assert d["liveness_threshold"] == THRESHOLD
    assert SPEC_DETAIL_KEYS <= set(d["details"])
    assert d["details"]["landmark_count"] == 468
    assert d["details"]["depth_quality"] in {"good", "moderate", "poor"}
    h = d["face_embedding_hash"]
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)


def test_no_raw_image_in_response(client, img):
    image_b64 = b64(img["obama"])
    r = client.post("/liveness/check", json={"challenge_response": image_b64, "challenge_type": "passive"})
    assert "data:image" not in r.text.lower()
    assert image_b64[:100] not in r.text


def test_hash_matches_enrollment(client, img):
    """
    Liveness hash uses the enrollment scheme: it is the same hash /face/verify
    computes for the same image, and verifying against the enrolled template
    accepts the same person and rejects a different one.
    """
    r = client.post("/face/enroll", json={"user_id": "liveness-test", "image": b64(img["obama"]), "camera_consent": True})
    assert r.status_code in (200, 201)
    enrolled = r.json()["face_template_hash"]

    for name, should_match in (("obama", True), ("obama2", True), ("biden", False)):
        live_hash = check(client, img[name])["face_embedding_hash"]
        v = client.post("/face/verify", json={"image": b64(img[name]), "reference_template_hash": enrolled})
        assert v.status_code == 200
        v = v.json()
        assert live_hash == v["current_template_hash"], f"{name}: liveness and verify hashes differ"
        assert v["match_passed"] is should_match, f"{name}: match_score {v['match_score']}"


def test_single_frame_challenge_is_not_claimed_verified(client, img):
    d = check(client, img["obama"], "blink")
    assert d["details"]["challenge_verified"] is False


# -----------------------------------------------------------------------------
# Spoofs and bad input fail
# -----------------------------------------------------------------------------

def test_no_face_fails_cleanly(client):
    d = check(client, np.full((256, 256, 3), (210, 170, 140), np.uint8))  # uniform skin tone
    assert d["liveness_passed"] is False
    assert d["liveness_score"] == 0.0
    assert d["face_embedding_hash"] == ""
    assert SPEC_DETAIL_KEYS <= set(d["details"])


@pytest.mark.parametrize("attack, indicator", [
    (blurred, "blurred_or_recaptured"),
    (grayscale, "grayscale_image"),
    (screen_replay, "screen_moire_pattern"),
])
@pytest.mark.parametrize("challenge", ["passive", "blink", "head_turn"])
def test_spoof_is_rejected(client, img, attack, indicator, challenge):
    d = check(client, attack(img["obama"]), challenge)
    assert d["liveness_passed"] is False
    assert d["liveness_score"] < THRESHOLD
    assert indicator in d["details"]["spoof_indicators"]


def test_invalid_base64_is_400(client):
    r = client.post("/liveness/check", json={"challenge_response": "!!not-base64", "challenge_type": "blink"})
    assert r.status_code == 400


def test_unknown_challenge_type_is_422(client, img):
    r = client.post("/liveness/check", json={"challenge_response": b64(img["obama"]), "challenge_type": "smile"})
    assert r.status_code == 422


def test_too_many_frames_is_422(client, img):
    frame = b64(img["obama"])
    r = client.post("/liveness/check", json={"challenge_response": frame, "challenge_type": "blink", "frames": [frame] * 11})
    assert r.status_code == 422


# -----------------------------------------------------------------------------
# Multi-frame challenges
# -----------------------------------------------------------------------------

def test_head_turn_sequence_passes(client, img):
    # obama2 is turned (yaw about -0.46); obama is frontal
    d = check(client, img["obama"], "head_turn", [img["obama"], img["obama2"], with_noise(img["obama"], 1)])
    assert d["details"]["challenge_verified"] is True
    assert d["details"]["challenge_passed"] is True
    assert d["liveness_passed"] is True


def test_still_photo_resent_fails(client, img):
    d = check(client, img["obama"], "head_turn", [img["obama"]] * 3)
    assert d["liveness_passed"] is False
    assert "static_frame_sequence" in d["details"]["spoof_indicators"]


def test_identity_swap_in_sequence_fails(client, img):
    d = check(client, img["obama"], "head_turn", [img["obama"], img["biden"], img["obama2"]])
    assert d["liveness_passed"] is False
    assert "identity_changed_in_sequence" in d["details"]["spoof_indicators"]


def test_blink_challenge_without_blink_fails(client, img):
    frames = [img["obama"], with_noise(img["obama"], 1), with_noise(img["obama"], 2)]
    d = check(client, img["obama"], "blink", frames)
    assert d["details"]["challenge_verified"] is True
    assert d["details"]["challenge_passed"] is False
    assert d["liveness_passed"] is False


def test_head_turn_without_turning_fails(client, img):
    frames = [img["obama"], with_noise(img["obama"], 1), with_noise(img["obama"], 2)]
    d = check(client, img["obama"], "head_turn", frames)
    assert d["details"]["challenge_passed"] is False
    assert d["liveness_passed"] is False


def test_frame_without_face_fails(client, img):
    no_face = np.full(img["obama"].shape, 128, np.uint8)
    d = check(client, img["obama"], "head_turn", [img["obama"], no_face, img["obama2"]])
    assert d["liveness_passed"] is False
    assert "face_missing_in_sequence" in d["details"]["spoof_indicators"]