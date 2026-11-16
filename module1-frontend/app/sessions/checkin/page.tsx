
'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { apiFetch, useAuth, isAuthenticated } from '@/app/components/AuthContext';
import { useFeedback } from '@/app/components/FeedbackContext';
import { queueCheckin } from '@/app/lib/offlineStorage';

const COUNTDOWN_SECONDS = 120;

type ProfileData = {
    camera_consent: boolean;
    geolocation_consent: boolean;
    face_enrolled: boolean;
};

type SessionData = {
    id: string;
    name: string;
    venue_name: string;
    status: string;
    checkin_opens_at: string;
    checkin_closes_at: string;
    venue_latitude: number;
    venue_longitude: number;
    geofence_radius_meters: number;
    require_liveness_check: boolean;
    require_face_match: boolean;
    qr_code_enabled: boolean;
};

type LocationData = {
    latitude: number;
    longitude: number;
    location_accuracy_meters: number;
};

type CheckinResponse = {
    id?: string;
    status?: string;
    [key: string]: unknown;
};

type ApiError = {
    detail?: string;
    message?: string;
};

function formatDateTime(value: string): string {
    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return value;
    }

    return new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
    }).format(date);
}

async function readError(response: Response, fallback: string): Promise<string> {
    try {
        const data = (await response.json()) as ApiError;
        return data.detail || data.message || fallback;
    } catch {
        return fallback;
    }
}

function getUserLocation(): Promise<LocationData> {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject(new Error('Geolocation is not supported by this browser.'));
            return;
        }

        navigator.geolocation.getCurrentPosition(
            position => {
                resolve({
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    location_accuracy_meters: position.coords.accuracy,
                });
            },
            error => {
                const message =
                    error.code === error.PERMISSION_DENIED
                        ? 'Location permission was denied. Allow location access in your browser settings.'
                        : error.code === error.TIMEOUT
                            ? 'Obtaining your location timed out. Please try again.'
                            : 'Unable to obtain your location. Please try again.';

                reject(new Error(message));
            },
            {
                enableHighAccuracy: true,
                timeout: 15000,
                maximumAge: 0,
            }
        );
    });
}

export default function CheckinPage() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const sessionId = searchParams.get('session-id');

    const { user } = useAuth();
    const { setMsg } = useFeedback();

    const [authChecked, setAuthChecked] = useState(false);
    const [accessDenied, setAccessDenied] = useState(false);
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState('');

    const [profile, setProfile] = useState<ProfileData | null>(null);
    const [session, setSession] = useState<SessionData | null>(null);

    const [location, setLocation] = useState<LocationData | null>(null);
    const [faceImage, setFaceImage] = useState<string | null>(null);
    const [qrCode, setQrCode] = useState<string | null>(null);

    const [locationLoading, setLocationLoading] = useState(false);
    const [cameraRunning, setCameraRunning] = useState(false);
    const [qrScanning, setQrScanning] = useState(false);
    const [submitting, setSubmitting] = useState(false);

    const [remainingSeconds, setRemainingSeconds] =
        useState(COUNTDOWN_SECONDS);

    const videoRef = useRef<HTMLVideoElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const faceStreamRef = useRef<MediaStream | null>(null);

    const qrScannerRef =
        useRef<import('html5-qrcode').Html5Qrcode | null>(null);

    const qrScannedRef = useRef(false);
    const deadlineRef = useRef<number | null>(null);
    const expiredRef = useRef(false);
    const submittingRef = useRef(false);

    const cameraRequired = Boolean(
        session?.require_liveness_check ||
        session?.require_face_match ||
        session?.qr_code_enabled
    );

    const eligibilityIssues = useMemo(() => {
        const issues: string[] = [];

        if (!profile || !session) {
            return issues;
        }

        if (!profile.geolocation_consent) {
            issues.push(
                'You must provide geolocation consent on your profile page before checking in.'
            );
        }

        if (cameraRequired && !profile.camera_consent) {
            issues.push(
                'You must provide camera consent on your profile page because this session requires camera access.'
            );
        }

        if (session.require_face_match && !profile.face_enrolled) {
            issues.push(
                'You must enroll your face on your profile page before checking in.'
            );
        }

        if (session.status !== 'active') {
            issues.push(
                'The check-in window is not currently open. The session status must be active.'
            );
        }

        return issues;
    }, [profile, session, cameraRequired]);

    const eligible =
        authChecked &&
        !accessDenied &&
        !loading &&
        !loadError &&
        Boolean(profile && session) &&
        eligibilityIssues.length === 0;

    const needsFaceImage = Boolean(
        session?.require_liveness_check || session?.require_face_match
    );

    const needsQr = Boolean(session?.qr_code_enabled);

    const allActionsCompleted =
        Boolean(location) &&
        (!needsFaceImage || Boolean(faceImage)) &&
        (!needsQr || Boolean(qrCode));

    // Authenticate and load the profile and session.
    useEffect(() => {
        let cancelled = false;

        async function loadData() {
            if (!isAuthenticated()) {
                if (!cancelled) {
                    setAccessDenied(true);
                    setAuthChecked(true);
                    setLoading(false);
                }
                return;
            }

            // AuthContext may still be restoring the user from storage.
            if (!user) {
                return;
            }

            if (user.role !== 'student') {
                if (!cancelled) {
                    setAccessDenied(true);
                    setAuthChecked(true);
                    setLoading(false);
                }
                return;
            }

            setAccessDenied(false);
            setAuthChecked(true);

            if (!sessionId) {
                if (!cancelled) {
                    setLoadError('Missing session-id in the URL.');
                    setLoading(false);
                }
                return;
            }

            setLoading(true);
            setLoadError('');

            try {
                const [profileResponse, sessionResponse] = await Promise.all([
                    apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/users/me`, {
                        method: 'GET',
                    }),
                    apiFetch(
                        `${process.env.NEXT_PUBLIC_API_BASE_URL}/sessions/${encodeURIComponent(sessionId)}`,
                        { method: 'GET' }
                    ),
                ]);

                if (!profileResponse.ok) {
                    throw new Error(
                        await readError(
                            profileResponse,
                            'Failed to load your profile.'
                        )
                    );
                }

                if (!sessionResponse.ok) {
                    throw new Error(
                        await readError(
                            sessionResponse,
                            'Failed to load session details.'
                        )
                    );
                }

                const profileData = (await profileResponse.json()) as ProfileData;
                const sessionData = (await sessionResponse.json()) as SessionData;

                if (cancelled) {
                    return;
                }

                setProfile({
                    camera_consent: profileData.camera_consent === true,
                    geolocation_consent:
                        profileData.geolocation_consent === true,
                    face_enrolled: profileData.face_enrolled === true,
                });

                setSession(sessionData);
            } catch (error) {
                if (!cancelled) {
                    setLoadError(
                        error instanceof Error
                            ? error.message
                            : 'Failed to load check-in information.'
                    );
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        }

        void loadData();

        return () => {
            cancelled = true;
        };
    }, [user, sessionId]);

    const stopFaceCamera = useCallback(() => {
        faceStreamRef.current?.getTracks().forEach(track => track.stop());
        faceStreamRef.current = null;

        if (videoRef.current) {
            videoRef.current.srcObject = null;
        }

        setCameraRunning(false);
    }, []);

    const stopQrScanner = useCallback(async () => {
        const scanner = qrScannerRef.current;

        if (!scanner) {
            setQrScanning(false);
            return;
        }

        qrScannerRef.current = null;

        try {
            await scanner.stop();
        } catch {
            // The scanner may already have stopped after a successful scan.
        }

        try {
            scanner.clear();
        } catch {
            // The scanner's DOM may already have been cleared.
        }

        setQrScanning(false);
    }, []);

    // Stop media resources when the page unmounts.
    useEffect(() => {
        return () => {
            faceStreamRef.current?.getTracks().forEach(track => track.stop());

            const scanner = qrScannerRef.current;
            qrScannerRef.current = null;

            if (scanner) {
                void scanner.stop()
                    .catch(() => { })
                    .then(() => {
                        try {
                            scanner.clear();
                        } catch {
                            // Ignore cleanup errors during unmount.
                        }
                    });
            }
        };
    }, []);

    // Start the two-minute deadline once the user becomes eligible.
    useEffect(() => {
        if (!eligible || expiredRef.current) {
            return;
        }

        if (deadlineRef.current === null) {
            deadlineRef.current = Date.now() + COUNTDOWN_SECONDS * 1000;
            setRemainingSeconds(COUNTDOWN_SECONDS);
        }

        const updateCountdown = () => {
            const deadline = deadlineRef.current;

            if (deadline === null || expiredRef.current) {
                return;
            }

            const remaining = Math.max(
                0,
                Math.ceil((deadline - Date.now()) / 1000)
            );

            setRemainingSeconds(remaining);

            if (remaining === 0) {
                expiredRef.current = true;

                setLocation(null);
                setFaceImage(null);
                setQrCode(null);

                faceStreamRef.current
                    ?.getTracks()
                    .forEach(track => track.stop());

                faceStreamRef.current = null;

                if (videoRef.current) {
                    videoRef.current.srcObject = null;
                }

                const scanner = qrScannerRef.current;
                qrScannerRef.current = null;

                if (scanner) {
                    void scanner.stop()
                        .catch(() => { })
                        .then(() => {
                            try {
                                scanner.clear();
                            } catch {
                                // Ignore cleanup errors.
                            }
                        });
                }

                setCameraRunning(false);
                setQrScanning(false);

                setMsg(
                    'Your two-minute check-in period has expired. Your captured data has been discarded.',
                    true
                );

                router.push(
                    `/sessions/details?id=${encodeURIComponent(sessionId ?? '')}`
                );
            }
        };

        updateCountdown();

        const interval = window.setInterval(updateCountdown, 250);

        return () => window.clearInterval(interval);
    }, [eligible, sessionId, router, setMsg]);

    async function handleGetLocation() {
        if (!eligible || expiredRef.current) {
            return;
        }

        setLocationLoading(true);

        try {
            const result = await getUserLocation();

            if (expiredRef.current) {
                return;
            }

            setLocation(result);
        } catch (error) {
            setMsg(
                error instanceof Error
                    ? error.message
                    : 'Unable to obtain your location.',
                true
            );
        } finally {
            setLocationLoading(false);
        }
    }

    async function handleStartFaceCamera() {
        if (!eligible || expiredRef.current) {
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: 'user',
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                },
                audio: false,
            });

            if (expiredRef.current) {
                stream.getTracks().forEach(track => track.stop());
                return;
            }

            faceStreamRef.current = stream;

            if (videoRef.current) {

                videoRef.current.srcObject = stream;
                await videoRef.current.play();
                setCameraRunning(true);

            }
        } catch {
            setMsg(
                'Unable to start the front-facing camera. Check your browser permissions and try again.',
                true
            );
        }
    }

    function handleCaptureFace() {
        if (!eligible || expiredRef.current) {
            return;
        }

        const video = videoRef.current;
        const canvas = canvasRef.current;

        if (!video || !canvas || video.videoWidth === 0) {
            setMsg('The camera is not ready to capture an image.', true);
            return;
        }

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        const context = canvas.getContext('2d');

        if (!context) {
            setMsg('Unable to capture the face image.', true);
            return;
        }

        context.drawImage(video, 0, 0, canvas.width, canvas.height);

        const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
        const base64Image = dataUrl.split(',')[1];

        if (!base64Image) {
            setMsg('Unable to encode the captured face image.', true);
            return;
        }

        setFaceImage(base64Image);
        stopFaceCamera();
    }

    async function handleStartQrScanner() {
        if (!eligible || expiredRef.current || qrScanning) {
            return;
        }

        try {
            // Dynamic import avoids loading the camera library during SSR.
            const { Html5Qrcode } = await import('html5-qrcode');

            if (expiredRef.current) {
                return;
            }

            qrScannedRef.current = false;

            const scanner = new Html5Qrcode('qr-reader');
            qrScannerRef.current = scanner;
            setQrScanning(true);

            await scanner.start(
                { facingMode: 'environment' },
                {
                    fps: 10,
                    qrbox: { width: 250, height: 250 },
                },
                decodedText => {
                    if (qrScannedRef.current || expiredRef.current) {
                        return;
                    }

                    qrScannedRef.current = true;
                    setQrCode(decodedText);

                    void stopQrScanner();
                },
                () => {
                    // A frame without a QR code is normal while scanning.
                }
            );

            // Handle expiry while the scanner was starting.
            if (expiredRef.current) {
                await stopQrScanner();
            }
        } catch {
            await stopQrScanner();

            if (!expiredRef.current) {
                setMsg(
                    'Unable to start the QR scanner. Check camera permissions and try again.',
                    true
                );
            }
        }
    }

    async function handleSubmit() {
        if (
            !eligible ||
            !allActionsCompleted ||
            !sessionId ||
            !location ||
            submittingRef.current ||
            expiredRef.current
        ) {
            return;
        }

        if (deadlineRef.current === null || Date.now() >= deadlineRef.current) {
            return;
        }

        submittingRef.current = true;
        setSubmitting(true);


        const device_fingerprint = localStorage.getItem('device_fingerprint');
        if (device_fingerprint === null) {
            throw new Error("Please register your device first")
        }

        try {
            const payload = {
                session_id: sessionId,
                latitude: location.latitude,
                longitude: location.longitude,
                location_accuracy_meters:
                    location.location_accuracy_meters,
                device_fingerprint: device_fingerprint,
                liveness_challenge_response: needsFaceImage
                    ? faceImage
                    : null,
                qr_code: needsQr ? qrCode : null,
            };

            let response: Response;

            try {
                response = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/checkins`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(payload),
                });

                if (response.status >= 500 || response.status === 404) {
                    throw new TypeError("There is a problem with the server");
                }
                else if (response.status === 429) {
                    throw new TypeError("Too many requests, please refresh your page in a few minutes to attempt resubmission.");
                }
            } catch (requestError) {
                // A native fetch network failure commonly throws TypeError.
                if (requestError instanceof TypeError) {
                    const queuedEntry = await queueCheckin(payload);
                    
                    if (queuedEntry === null) {
                        setMsg(
                            "A check-in for this session is already pending and will be retried when connectivity returns.\nDetails: " + requestError.message,
                            true
                        );
                    } else {
                        setMsg(
                            "Unable to reach the server. Your check-in has been saved locally and will be retried when connectivity returns.\nDetails: " + requestError.message,
                            false
                        );
                        
                    }
                    router.back();
                    return;
                }

                throw requestError;
            }

            let data: CheckinResponse;

            try {
                data = (await response.json()) as CheckinResponse;
            } catch {
                throw new Error('The server returned an invalid response.');
            }

            if (!response.ok) {

                throw new Error(
                    await Promise.resolve(
                        (data as ApiError).detail ||
                        `Check-in failed (HTTP ${response.status}).`
                    )
                );
            }

            if (typeof data.id !== 'string' || data.id.length === 0) {
                throw new Error(
                    'The server response did not contain a valid check-in ID.'
                );
            }

            // Do not navigate to success if the deadline passed during submission.
            if (
                expiredRef.current ||
                deadlineRef.current === null ||
                Date.now() >= deadlineRef.current
            ) {
                return;
            }

            expiredRef.current = true;

            setMsg('Check-in submitted successfully.', false);

            router.push(
                `/checkins/details?id=${encodeURIComponent(data.id)}`
            );
        } catch (error) {
            if (!expiredRef.current) {
                setMsg(
                    error instanceof Error
                        ? error.message
                        : 'Check-in failed. Please try again.',
                    true
                );
            }
        } finally {
            submittingRef.current = false;
            setSubmitting(false);
        }
    }

    if (!authChecked || loading) {
        return (
            <main className="min-h-screen bg-gray-100 p-4">
                <div className="mx-auto max-w-2xl rounded-lg bg-white p-6 shadow-sm">
                    <p className="text-sm text-gray-600">
                        Loading check-in information...
                    </p>
                </div>
            </main>
        );
    }

    if (accessDenied) {
        return (
            <main className="min-h-screen bg-gray-100 p-4">
                <div
                    role="alert"
                    className="mx-auto max-w-2xl rounded-lg border border-red-200 bg-red-50 p-6"
                >
                    <h1 className="text-xl font-semibold text-red-800">
                        Student access required
                    </h1>
                    <p className="mt-2 text-sm text-red-700">
                        Only authenticated students are allowed to check in.
                        You cannot proceed with this page.
                    </p>
                </div>
            </main>
        );
    }

    return (
        <main className="min-h-screen bg-gray-100 p-4">
            <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 py-6">
                <header>
                    <h1 className="text-2xl font-semibold text-gray-900">
                        Session check-in
                    </h1>
                    <p className="mt-1 text-sm text-gray-600">
                        Complete the required steps before the countdown expires.
                    </p>
                </header>

                {loadError && (
                    <div
                        role="alert"
                        className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700"
                    >
                        {loadError}
                    </div>
                )}

                {session && (
                    <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
                        <h2 className="text-lg font-semibold text-gray-900">
                            {session.name}
                        </h2>

                        <dl className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
                            <div>
                                <dt className="text-sm text-gray-500">
                                    Venue
                                </dt>
                                <dd className="mt-1 font-medium text-gray-900">
                                    {session.venue_name}
                                </dd>
                            </div>

                            <div>
                                <dt className="text-sm text-gray-500">
                                    Status
                                </dt>
                                <dd className="mt-1 font-medium text-gray-900">
                                    {session.status}
                                </dd>
                            </div>

                            <div>
                                <dt className="text-sm text-gray-500">
                                    Check-in opens
                                </dt>
                                <dd className="mt-1 text-sm text-gray-800">
                                    {formatDateTime(session.checkin_opens_at)}
                                </dd>
                            </div>

                            <div>
                                <dt className="text-sm text-gray-500">
                                    Check-in closes
                                </dt>
                                <dd className="mt-1 text-sm text-gray-800">
                                    {formatDateTime(session.checkin_closes_at)}
                                </dd>
                            </div>
                        </dl>
                    </section>
                )}

                {profile && session && eligibilityIssues.length > 0 && (
                    <section
                        role="alert"
                        className="rounded-lg border border-amber-300 bg-amber-50 p-5"
                    >
                        <h2 className="font-semibold text-amber-900">
                            You cannot check in yet
                        </h2>
                        <p className="mt-1 text-sm text-amber-800">
                            Resolve all of the following requirements before
                            proceeding:
                        </p>
                        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-amber-900">
                            {eligibilityIssues.map(issue => (
                                <li key={issue}>{issue}</li>
                            ))}
                        </ul>
                    </section>
                )}

                {session && profile && (
                    <section
                        aria-label="Check-in tasks"
                        className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm"
                    >
                        <div className="mb-6 flex items-center justify-between gap-4">
                            <div>
                                <h2 className="text-lg font-semibold text-gray-900">
                                    Check-in tasks
                                </h2>
                                <p className="mt-1 text-sm text-gray-600">
                                    Your progress is kept on this page until
                                    submission or expiry.
                                </p>
                            </div>

                            {eligible && (
                                <div
                                    role="timer"
                                    aria-live="off"
                                    className={`shrink-0 rounded-md px-3 py-2 text-center font-mono text-lg font-semibold ${remainingSeconds <= 20
                                        ? 'bg-red-100 text-red-700'
                                        : 'bg-gray-100 text-gray-900'
                                        }`}
                                >
                                    {Math.floor(remainingSeconds / 60)}:
                                    {String(remainingSeconds % 60).padStart(2, '0')}
                                </div>
                            )}
                        </div>

                        {/* Location */}
                        <div className="border-t border-gray-200 py-5">
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                <div className="flex-1">
                                    <h3 className="font-medium text-gray-900">
                                        1. Capture your location
                                    </h3>
                                    <p className="mt-1 text-sm text-gray-600">
                                        Allow the browser to obtain your current
                                        coordinates and estimated location accuracy.
                                    </p>

                                    {location && (
                                        <div className="mt-3 rounded-md bg-gray-50 p-3 text-sm text-gray-700">
                                            <p>
                                                Latitude: {location.latitude}
                                            </p>
                                            <p>
                                                Longitude: {location.longitude}
                                            </p>
                                            <p>
                                                Accuracy: approximately{' '}
                                                {location.location_accuracy_meters.toFixed(1)} m
                                            </p>
                                        </div>
                                    )}
                                </div>

                                <div className="flex shrink-0 flex-col items-start gap-2">
                                    <button
                                        type="button"
                                        disabled={!eligible || locationLoading || submitting}
                                        onClick={handleGetLocation}
                                        className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-400"
                                    >
                                        {locationLoading
                                            ? 'Obtaining location...'
                                            : location
                                                ? 'Refresh location'
                                                : 'Get location'}
                                    </button>

                                    {location && (
                                        <span className="text-sm font-medium text-green-700">
                                            ✓ Completed
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Face image */}
                        {needsFaceImage && (
                            <div className="border-t border-gray-200 py-5">
                                <div className="flex flex-col gap-3">
                                    <h3 className="font-medium text-gray-900">
                                        2. Capture your face
                                    </h3>
                                    <p className="text-sm text-gray-600">
                                        Start the front-facing camera, position
                                        your face clearly in the frame, and capture
                                        a still image. The camera stops after
                                        capture. You may retake the image.
                                    </p>


                                    <video
                                        ref={videoRef}
                                        autoPlay
                                        playsInline
                                        muted
                                        className="w-full max-w-md rounded-md bg-black"
                                    />


                                    <canvas
                                        ref={canvasRef}
                                        className={`h-auto w-full max-w-md rounded-md ${faceImage ? 'block' : 'hidden'
                                            }`}
                                    />

                                    <div className="flex flex-wrap items-center gap-3">
                                        {!cameraRunning ? (
                                            <button
                                                type="button"
                                                disabled={!eligible || submitting}
                                                onClick={() => {
                                                    setCameraRunning(true);
                                                    handleStartFaceCamera();
                                                }}
                                                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-400"
                                            >
                                                Start front camera
                                            </button>
                                        ) : (
                                            <>
                                                <button
                                                    type="button"
                                                    disabled={!eligible || submitting}
                                                    onClick={handleCaptureFace}
                                                    className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-400"
                                                >
                                                    Capture frame
                                                </button>

                                                <button
                                                    type="button"
                                                    disabled={submitting}
                                                    onClick={stopFaceCamera}
                                                    className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:bg-gray-100"
                                                >
                                                    Stop camera
                                                </button>
                                            </>
                                        )}

                                        {faceImage && (
                                            <span className="text-sm font-medium text-green-700">
                                                ✓ Image captured
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* QR scanner */}
                        {needsQr && (
                            <div className="border-t border-gray-200 py-5">
                                <div className="flex flex-col gap-3">
                                    <h3 className="font-medium text-gray-900">
                                        {needsFaceImage
                                            ? '3. Scan the session QR code'
                                            : '2. Scan the session QR code'}
                                    </h3>
                                    <p className="text-sm text-gray-600">
                                        Start the environment-facing camera and
                                        point it at the QR code displayed at the
                                        venue. The scanner stops when a code is
                                        decoded. You may scan again to replace it.
                                    </p>

                                    <div
                                        id="qr-reader"
                                        className={`w-full max-w-md overflow-hidden rounded-md ${qrScanning ? '' : 'hidden'
                                            }`}
                                    />

                                    <div className="flex flex-wrap items-center gap-3">
                                        <button
                                            type="button"
                                            disabled={!eligible || qrScanning || submitting}
                                            onClick={handleStartQrScanner}
                                            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-400"
                                        >
                                            {qrScanning
                                                ? 'Scanning QR code...'
                                                : qrCode
                                                    ? 'Scan again'
                                                    : 'Start QR scanner'}
                                        </button>

                                        {qrScanning && (
                                            <button
                                                type="button"
                                                disabled={submitting}
                                                onClick={() => void stopQrScanner()}
                                                className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:bg-gray-100"
                                            >
                                                Stop scanner
                                            </button>
                                        )}

                                        {qrCode && (
                                            <span className="text-sm font-medium text-green-700">
                                                ✓ QR code scanned
                                            </span>
                                        )}
                                    </div>

                                    {qrCode && (
                                        <p className="break-all rounded-md bg-gray-50 p-3 text-sm text-gray-600">
                                            Decoded QR value: {qrCode}
                                        </p>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Submit */}
                        <div className="border-t border-gray-200 pt-5">
                            <p className="mb-3 text-sm text-gray-600">
                                {allActionsCompleted
                                    ? 'All required tasks are complete. Submit your check-in before the countdown expires.'
                                    : 'Complete every required task to enable submission.'}
                            </p>

                            <button
                                type="button"
                                disabled={
                                    !eligible ||
                                    !allActionsCompleted ||
                                    submitting ||
                                    remainingSeconds <= 0
                                }
                                onClick={handleSubmit}
                                className="w-full rounded-md bg-green-600 px-4 py-3 font-semibold text-white hover:bg-green-700 disabled:cursor-not-allowed disabled:bg-gray-400"
                            >
                                {submitting
                                    ? 'Submitting check-in...'
                                    : 'Submit check-in'}
                            </button>
                        </div>
                    </section>
                )}
            </div>
        </main>
    );
}
