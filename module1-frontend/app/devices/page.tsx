"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { formatDate } from "../lib/utils";
import { useAuth, apiFetch } from "../components/AuthContext";
import { useFeedback } from "../components/FeedbackContext"

export type Device = {
    id: string,
    device_name: string,
    platform: string,
    is_trusted: boolean,
    trust_score: string,
    is_active: boolean,
    first_seen_at: string,
    last_seen_at: string,
    total_checkins: number
}

export default function DevicesPage() {

    const [deviceList, setDeviceList] = useState<Device[]>([]);
    const [loading, setLoading] = useState(false);
    const { user, isAuthenticated } = useAuth();
    const router = useRouter();
    const { setMsg } = useFeedback();
    const [deviceID, setDeviceID] = useState("");


    const fetchData = async () => {

        setLoading(true)

        try {

            const response = await apiFetch(
                `${process.env.NEXT_PUBLIC_API_BASE_URL}/devices/my-devices`,
                { method: 'GET' }
            );

            const data = await response.json();

            if (!response.ok) {
                throw new Error(`Error: (${response.status}) ${data.detail || "Devices failed to load"}`)
            }

            setDeviceList(data as Device[]);
            setMsg("", true);

        } catch (error) {
            setMsg((error instanceof Error) ? error.message : "Devices failed to load", true);
            setDeviceList([]);

        }

        setLoading(false);

    }

    useEffect(() => {
        setDeviceID(localStorage.getItem('device_id') ?? "");
        fetchData();
    }, [isAuthenticated])




    if (!isAuthenticated()) {
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


    return (

        <main className="flex flex-col min-h-screen w-full bg-white p-4">

            <h1 className="text-4xl font-bold mt-8 mb-8 w-full text-center">
                My devices
            </h1>

            <section
                aria-label="Devices"
                aria-busy={loading}
                className="min-h-0 flex-1 overflow-y-auto rounded-xl">
                {loading ? (
                    <p className="py-8 text-center text-gray-500">
                        Loading devices...
                    </p>
                ) : deviceList.length === 0 ? (
                    <p className="py-8 text-center text-gray-500">
                        You haven't registered any devices yet.
                    </p>
                ) : (
                    <div className="space-y-3 pb-4">
                        {deviceList.map((device) => (
                            <button
                                key={device.id}
                                type="button"
                                onClick={() => router.push(`/devices/details?id=${encodeURIComponent(device.id)}`)}
                                className="block w-full rounded-xl border border-gray-200 bg-white p-4 disabled:cursor-not-allowed
                                            text-left shadow-sm transition hover:border-blue-300 hover:shadow-md
                                            focus:outline-none focus:ring-2 focus:ring-blue-500">

                                <div className="flex flex-wrap items-start justify-between gap-3">
                                    <div className="min-w-0">
                                        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                                            ID: {device.id}
                                        </p>
                                        <h2 className="mt-1 text-lg font-semibold text-gray-900">
                                            Name: {device.device_name}
                                        </h2>
                                        {deviceID === device.id && (
                                            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                                                This device
                                            </p>
                                        )}
                                    </div>

                                    <span
                                        className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${device.is_active
                                            ? 'bg-green-100 text-green-800'
                                            : 'bg-red-100 text-red-800'}`}>
                                        {device.is_active ? "Active" : "Deactived"}
                                    </span>
                                </div>

                                <div className="mt-3 space-y-2 text-sm text-gray-600">

                                    <p>
                                        <span className="font-medium text-gray-800">
                                            First seen:
                                        </span>{' '}
                                        {formatDate(device.first_seen_at)}
                                    </p>

                                    <p>
                                        <span className="font-medium text-gray-800">
                                            Last seen:
                                        </span>{' '}
                                        {formatDate(device.last_seen_at)}
                                    </p>

                                </div>
                            </button>
                        ))}
                    </div>
                )}
            </section>


            <div className="flex flex-row w-full pt-8 justify-evenly">
                {deviceID === "" && (
                    <button type="button" onClick={() => router.push('/devices/register')}
                        className="text-lg w-fit text-center p-4 mb-8 font-bold shadow-2xl text-white rounded-lg bg-blue-500 hover:bg-blue-700">
                        Register your device
                    </button>
                )}

                {(user?.role === "admin") && (
                    <button type="button" onClick={() => router.push('/devices/admin')}
                        className="text-lg w-fit text-center p-4 mb-8 font-bold shadow-2xl text-white rounded-lg bg-blue-500 hover:bg-blue-700">
                        Adminstrator options
                    </button>
                )}

            </div>

        </main>

    );
}