"use client";

import { useAuth, apiFetch } from "@/app/components/AuthContext";
import { useRouter } from "next/navigation";
import { useState, useEffect, useRef } from 'react';
import { useFeedback } from "@/app/components/FeedbackContext";

export default function EnrollFacePage() {

    const { isAuthenticated } = useAuth();
    const { setMsg } = useFeedback();
    const router = useRouter();

    const [enrolled, setEnrolled] = useState(false);
    const [camera, setCamera] = useState(false);
    const [errorMessage, setErrorMessage] = useState("");
    const [cameraActive, setCameraActive] = useState(false);
    const [startingCamera, setStartingCamera] = useState(false)
    const [submitting, setSubmitting] = useState(false)

    const videoRef = useRef<HTMLVideoElement>(null)
    const canvasRef = useRef<HTMLCanvasElement>(null)
    const streamRef = useRef<MediaStream | null>(null)


    const fetchData = async () => {
        const response = await apiFetch(
            `${process.env.NEXT_PUBLIC_API_BASE_URL}/users/me`,
            { method: 'GET' }
        );

        try {
            const { camera_consent, face_enrolled } = await response.json();

            setCamera(camera_consent);
            setEnrolled(face_enrolled);
        } catch {
            setMsg("Profile failed to load", true);
            setCamera(false);
            setEnrolled(false);
        }
    }

    fetchData();

    useEffect(() => {

        if (!isAuthenticated()) {
            setErrorMessage("You need to be logged in to access this page");
        }
        else if (enrolled) {
            setErrorMessage("Your face has already been enrolled");
        }
        else if (!camera) {
            setErrorMessage("You need to grant permission for camera access in the profile page");
        }
        else {
            setErrorMessage("");
        }

    }, [enrolled, isAuthenticated, camera])



    if (errorMessage !== "") {
        return (

            <main className="flex min-h-screen flex-col items-center justify-center bg-gray-100">
                <div className="flex flex-col w-1/2 p-2 bg-red-600 max-w-md items-center rounded-lg shadow-2xl">
                    <h1 className="text-4xl font-bold w-full text-center text-white m-8">
                        {errorMessage}
                    </h1>

                    {!isAuthenticated() && (
                        <div className="flex w-full mb-4 flex-row justify-evenly mt-auto">
                            <button className="text-lg w-1/4 text-center p-4 font-bold shadow-2xl rounded-lg bg-white hover:bg-gray-100"
                                type="button" onClick={() => router.push('/login')}>
                                Log in
                            </button>
                            <button className="text-lg w-1/4 text-center p-4 font-bold shadow-2xl rounded-lg bg-white hover:bg-gray-100"
                                type="button" onClick={() => router.push('/register')}>
                                Register
                            </button>
                        </div>
                    )}
                </div>
            </main>

        );
    }

    function stopCamera() {
        streamRef.current?.getTracks().forEach((track) => track.stop())
        streamRef.current = null

        if (videoRef.current) {
            videoRef.current.srcObject = null
        }

        setCameraActive(false)
    }

    async function startCamera() {
        setStartingCamera(true)

        try {
            if (!navigator.mediaDevices?.getUserMedia) {
                throw new Error(
                    'Camera access is unavailable. Use HTTPS or localhost and a supported browser.',
                )
            }

            // Release any previous stream before requesting another one.
            stopCamera()

            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: 'user',
                },
                audio: false,
            })

            streamRef.current = stream

            if (!videoRef.current) {
                stream.getTracks().forEach((track) => track.stop())
                streamRef.current = null
                return
            }

            videoRef.current.srcObject = stream
            await videoRef.current.play()

            setCameraActive(true)
            //setEnrollment(null)
            setMsg('', false)
        } catch (error) {
            stopCamera()

            const message = error instanceof Error ? error.message : 'Unable to access the camera.';

            setMsg(message, true)
        } finally {
            setStartingCamera(false)
        }
    }

    async function captureAndEnroll() {
        const video = videoRef.current
        const canvas = canvasRef.current

        if (
            !video ||
            !canvas ||
            !streamRef.current ||
            video.videoWidth === 0 ||
            video.videoHeight === 0
        ) {
            setMsg('The camera is not ready. Please start it again.', true)
            return
        }

        setSubmitting(true)

        try {
            // Draw the current video frame onto the canvas.
            canvas.width = video.videoWidth
            canvas.height = video.videoHeight

            const context = canvas.getContext('2d')

            if (!context) {
                throw new Error('Unable to capture an image from the camera.')
            }

            context.drawImage(video, 0, 0, canvas.width, canvas.height)
            // Export as JPEG and remove the data URL prefix.
            const dataUrl = canvas.toDataURL('image/jpeg', 0.9)
            const base64Image = dataUrl.split(',')[1]

            if (!base64Image) {
                throw new Error('Failed to encode the captured image.')
            }

            const response = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/users/me/face/enroll`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    image: base64Image,
                }),
            })

            if (!response.ok) {
                if (response.status === 400) {
                    throw new Error('Face enrollment failed. Check your camera consent and ensure your face is visible.')
                }

                if (response.status === 503) {
                    throw new Error('The face recognition service is unavailable. Please try again later.')
                }
                throw new Error(`Face enrollment failed (HTTP ${response.status}).`)
            }

            const { success, message, face_enrolled, quality_score } = await response.json();

            setMsg(message + "\nQuality score: " + quality_score, !success);

            if (face_enrolled) {
                stopCamera();
                router.push('/profile');
            }


        }
        catch (error) {
            const e = error instanceof Error ? error.message : "Login failed, something went wrong.";
            setMsg(e, true);
            console.error(e);
        }
        finally {
            setSubmitting(false);
        }
    }

    return (
        <main className="mx-auto max-w-2xl space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Face Enrollment</h1>
                <p className="mt-2 text-sm text-gray-600">
                    Capture an image of your face to enroll it for future facial verification.
                </p>
            </div>

            <div className="rounded-lg border border-gray-200 p-4">
                <div className="overflow-hidden rounded-md bg-black">

                    <video ref={videoRef} autoPlay playsInline muted
                        className="aspect-[4/3] w-full object-cover" />

                    {!cameraActive && (
                        <div className="flex aspect-[4/3] items-center justify-center text-center text-sm text-white">
                            Camera is off
                        </div>
                    )}
                </div>

                <canvas ref={canvasRef} className="hidden" />

                <p className="mt-3 text-sm text-gray-600">
                    For the best results, position your face in the centre of the frame and ensure that the lighting is adequate
                </p>


                <div className="mt-4 flex flex-wrap gap-3">
                    {!cameraActive && (
                        <button
                            type="button"
                            onClick={startCamera}
                            disabled={startingCamera || submitting}
                            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50">
                            {startingCamera ? 'Starting camera...' : 'Start camera'}
                        </button>
                    )}

                    {cameraActive && (
                        <>
                            <button
                                type="button"
                                onClick={captureAndEnroll}
                                disabled={submitting}
                                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                {submitting ? 'Enrolling...' : 'Capture and enroll'}
                            </button>

                            <button
                                type="button"
                                onClick={stopCamera}
                                disabled={submitting}
                                className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium hover:bg-gray-50 disabled:opacity-50">
                                Stop camera
                            </button>
                        </>
                    )}
                </div>

            </div>

        </main>
    );
}