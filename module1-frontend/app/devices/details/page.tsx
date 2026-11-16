"use client";

import { apiFetch, useAuth } from "@/app/components/AuthContext";
import { useSearchParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { type Device } from "../page";
import { useFeedback } from "@/app/components/FeedbackContext";
import { formatDate } from "@/app/lib/utils";

export default function DeviceDetails() {

    const { user, isAuthenticated } = useAuth();
    const searchParams = useSearchParams();
    const [isEditing, setEditing] = useState(false);
    const [device, setDevice] = useState<Device | null>(null);
    const [editDevice, setEditDevice] = useState<Device | null>(null);
    const { setMsg } = useFeedback();
    const router = useRouter();
    const [id, setID] = useState(searchParams.get('id'));
    const [deleteDevice, setDelete] = useState(false);

    const fetchData = async () => {

        try {

            if (!id) {
                throw new Error("Invalid session ID");
            }

            const response = await apiFetch(
                `${process.env.NEXT_PUBLIC_API_BASE_URL}/devices/my-devices`,
                { method: 'GET' }
            );

            const data = await response.json();

            if (!response.ok) {
                throw new Error(`Error: (${response.status}) ${data.detail || "Devices failed to load"}`)
            }

            let flag = false;

            for (const dev of data as Device[]) {
                if (dev.id === id) {
                    setDevice(dev as Device);
                    setEditDevice(dev as Device);
                    flag = true;
                    break;
                }
            }

            if (!flag) {
                throw new Error("Error: Device not found");
            }

            setMsg("", true);

        } catch (error) {
            setMsg((error instanceof Error) ? error.message : "Devices failed to load", true);
            setDevice(null);
            setEditDevice(null);
        }


    }



    async function submit() {
        try {

            let saveChanges = null;

            if (deleteDevice) {
                saveChanges = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/devices/` + device?.id, {
                    method: 'DELETE',
                });
            }
            else {
                saveChanges = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/devices/` + device?.id, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        device_name: editDevice?.device_name,
                        is_active: editDevice?.is_active
                    })
                });
            }

            if (!saveChanges.ok) {
                const data = await saveChanges.json();
                if (saveChanges.status === 401) {
                    setMsg(data.detail || "Invalid credentials", true);
                }
                else if (saveChanges.status === 403) {
                    setMsg(data.detail || "Account disabled", true);
                }
                else {
                    setMsg(data.detail || "Request failed", true);
                    throw new Error(data.detail || 'Request failed');
                }
                return;
            }

            setMsg("Changes saved successfully", false);

            if (deleteDevice) {
                router.push("/devices");
            }
            else {
                fetchData();
            }

        } catch {
            setMsg("Changes failed to save", true);
            console.error('Changes failed to save');
        }

    }



    useEffect(() => {
        setID(searchParams.get('id'))
        if (id && isAuthenticated())
            fetchData();
    }, [isAuthenticated, user])

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
        <main className="flex flex-col w-full bg-white p-4">


            <h1 className="text-4xl font-bold mt-8 mb-8 w-full text-center">
                <input type="text" className="rounded-md enabled:border disabled:bg-transparent text-center
                         enabled:border-gray-300 focus:border-blue-500 focus:outline-none focus:ring-1
                          focus:ring-blue-500"
                    disabled={!isEditing}
                    value={editDevice?.device_name}
                    onChange={(event) => setEditDevice((prev) => prev ? { ...prev, device_name: event.target.value } : null)}>
                </input>
            </h1>

            <div className="grid gap-x-10 place-self-center grid-cols-1 lg:grid-cols-2 mt-3 space-y-2 text-sm text-gray-600">

                <>
                    <p>
                        <span className="font-medium text-gray-800">
                            Device ID:
                        </span>{' '}
                        {device?.id}
                    </p>
                    <p>
                        <span className="font-medium text-gray-800">
                            Platform:
                        </span>{' '}
                        {device?.platform}
                    </p>
                    <p>
                        <span className="font-medium text-gray-800">
                            Trusted:
                        </span>{' '}
                        {String(device?.is_trusted)}
                    </p>
                    <p>
                        <span className="font-medium text-gray-800">
                            Trust score:
                        </span>{' '}
                        {device?.trust_score}
                    </p>
                </>
                <>
                    <p>
                        <span className="font-medium text-gray-800">
                            Active:
                        </span>{' '}
                        <input type="checkbox" id="camera" name="camera" checked={editDevice?.is_active} disabled={!isEditing}
                            onChange={(event) => setEditDevice((prev) => prev ? { ...prev, is_active: event.target.checked } : null)}
                            className="h-4 w-4 rounded">
                        </input>
                    </p>
                    <p>
                        <span className="font-medium text-gray-800">
                            First seen:
                        </span>{' '}
                        {formatDate(device ? device.first_seen_at : "1970-01-01T00:00:00Z")}
                    </p>
                    <p>
                        <span className="font-medium text-gray-800">
                            Last seen:
                        </span>{' '}
                        {formatDate(device ? device.last_seen_at : "1970-01-01T00:00:00Z")}
                    </p>
                    <p>
                        <span className="font-medium text-gray-800">
                            Total checkins:
                        </span>{' '}
                        {device?.total_checkins}
                    </p>
                </>
            </div>


            <div className="flex flex-row w-full pt-8 justify-evenly">
                {!isEditing && (
                    <button type="button" onClick={() => setEditing(!isEditing)}
                        className="text-lg w-1/4 text-center p-4 font-bold shadow-2xl rounded-lg bg-blue-500 hover:bg-gray-100">
                        Edit
                    </button>
                )}

                {isEditing && (
                    <>
                        <button className="text-md max-h-full text-center p-4 font-bold shadow-2xl rounded-lg bg-blue-500 hover:bg-blue-700 text-white"
                            type="button" onClick={() => {
                                setEditing(false);
                                setEditDevice(device);
                            }}>
                            Cancel
                        </button>

                        <button className="text-md max-h-full text-center p-4 font-bold shadow-2xl rounded-lg bg-blue-500 hover:bg-blue-700 text-white disabled:bg-gray-400"
                            type="button" onClick={() => {
                                submit();
                                setEditing(false);
                            }}>
                            Save changes
                        </button>

                        <button className={`text-md max-h-full text-center p-4 font-bold shadow-2xl rounded-lg
                        ${deleteDevice ? 'bg-red-500 hover:bg-red-700 text-white' : 'bg-blue-500 hover:bg-blue-700 text-white'}`}
                            type="button" onClick={() => { setDelete(!deleteDevice) }}>
                            Delete device
                        </button>

                    </>
                )}

            </div>


        </main>
    );
}