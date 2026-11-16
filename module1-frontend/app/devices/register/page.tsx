"use client";

import { useAuth, apiFetch } from "@/app/components/AuthContext";
import { useRouter } from "next/navigation";
import { useState, FormEvent } from "react";
import { useFeedback } from "@/app/components/FeedbackContext";


export default function DeviceDetailsPage() {

    const { isAuthenticated } = useAuth();
    const router = useRouter();
    const { setMsg } = useFeedback();
    const [device_name, setName] = useState("");
    const [device_fingerprint, setFingerprint] = useState<string | null>(localStorage.getItem('device_fingerprint'));
    const [platform, setPlatform] = useState("");


    if (!isAuthenticated) {
        return (
            <main className="flex min-h-screen flex-col items-center justify-center bg-gray-100">
                <div className="flex flex-col w-1/2 p-2 bg-red-600 max-w-md items-center rounded-lg shadow-2xl">
                    <h1 className="text-4xl font-bold w-full text-center text-white m-8">
                        You need to be logged in to access this page
                    </h1>

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
                </div>
            </main>
        );
    }


    async function generateDevicePublicKey(): Promise<string> {
        const keyPair = await crypto.subtle.generateKey(
            {
                name: 'ECDSA',
                namedCurve: 'P-256',
            },
            false,
            ['sign', 'verify'],
        );

        const exported = await crypto.subtle.exportKey(
            'spki',
            keyPair.publicKey,
        );

        const bytes = new Uint8Array(exported);
        let binary = '';

        for (const byte of bytes) {
            binary += String.fromCharCode(byte);
        }

        const base64 = btoa(binary);
        const lines = base64.match(/.{1,64}/g)?.join('\n') ?? base64;

        return [
            '-----BEGIN PUBLIC KEY-----',
            lines,
            '-----END PUBLIC KEY-----',
        ].join('\n');
    }


    async function handleSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();

        setMsg("", true);

        try {

            const newFingerprint = crypto.randomUUID();

            // TODO: how to implement ts?
            // Need to store private key for later or nah
            const publicKey = await generateDevicePublicKey();

            const response = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/devices/register`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        device_fingerprint: newFingerprint,
                        device_name: device_name,
                        platform: platform,
                        public_key: publicKey
                    }),
                    cache: "no-store",
                }
            )

            const data = await response.json();

            if (!response.ok) {
                throw new Error(`(${response.status}): ${data.detail ? data.detail : "Error registering device"}`);
            }

            const { id } = data;

            setMsg("Device registered successfully with ID " + id, false);
            localStorage.setItem('device_fingerprint', newFingerprint);
            localStorage.setItem('device_id', id);

            router.push('/devices');

        } catch (error) {
            setMsg((error instanceof Error) ? error.message : "Error registering device", true);
        }
    }


    return (

        <main className="flex flex-col min-h-screen w-full items-center bg-gray-200 p-4">

            <form
                onSubmit={handleSubmit}
                className="w-full max-w-md space-y-6 rounded-lg bg-white p-8 shadow-md">
                <h1 className="text-center text-3xl font-bold">
                    Register your device
                </h1>

                <div>
                    <label
                        htmlFor="device_name"
                        className="mb-1 block text-sm font-medium text-gray-700">
                        {device_fingerprint ? "Your device has already been registered" : "Give your device a name"}
                    </label>

                    <input
                        id="device_name"
                        type="text"
                        disabled={!(device_fingerprint === null)}
                        value={device_name}
                        onChange={(event) => setName(event.target.value)}
                        required
                        className="w-full rounded-md border border-gray-300 px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    />

                    {device_fingerprint === null && (
                        <>
                            <label
                                htmlFor="device_platform"
                                className="mt-4 mb-1 block text-sm font-medium text-gray-700">
                                What are you using to access SAIV?
                            </label>
                            <select
                                id="device_platform"
                                value={platform}
                                onChange={(event) => setPlatform(event.target.value)}
                                required
                                className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500">
                                <option value="">Select a platform</option>
                                <option value="ios">IOS</option>
                                <option value="android">Android</option>
                                <option value="web">Web</option>
                                <option value="desktop">Desktop</option>
                            </select>
                        </>
                    )}

                </div>

                <button
                    type="submit"
                    disabled={!(device_fingerprint === null)}
                    className="w-full disabled:bg-gray-400 rounded-md bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700">
                    Register
                </button>

            </form>

        </main>

    );
}