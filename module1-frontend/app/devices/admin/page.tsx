"use client";

import { useState } from "react";
import { apiFetch, useAuth } from "@/app/components/AuthContext";
import { useFeedback } from "@/app/components/FeedbackContext";


export default function DevicesAdmin() {

    const [trusted, setTrusted] = useState(false);
    const [active, setActive] = useState(false);
    const [deviceID, setID] = useState("");
    const { setMsg } = useFeedback();
    const { user, isAuthenticated } = useAuth();
    const [isDeleting, setDeleting] = useState(false);

    async function deleteDevice() {

        setMsg("", true);

        try {

            const saveChanges = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/devices/` + deviceID, {
                method: 'DELETE',
            });

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

            setMsg("Device deleted successfully", false);

        } catch {
            setMsg("Failed to delete device", true);
            console.error('Failed to delete device');
        }
        setDeleting(false);
    }

    async function saveChanges() {

        setMsg("", true);

        try {

            const saveChanges = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/devices/` + deviceID, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    is_trusted: trusted,
                    is_active: active
                })
            });


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

        } catch {
            setMsg("Changes failed to save", true);
            console.error('Changes failed to save');
        }

    }

    if (!isAuthenticated() || user?.role !== "admin") {
        return (

            <main className="flex min-h-screen flex-col items-center justify-center bg-gray-100">
                <div className="flex flex-col w-1/2 p-2 bg-red-600 max-w-md items-center rounded-lg shadow-2xl">
                    <h1 className="text-4xl font-bold w-full text-center text-white m-8">
                        You need to be an administrator to access this page
                    </h1>
                </div>
            </main>

        );
    }


    return (


        <main className="min-h-screen w-full bg-gray-100 p-4">
            <div className="mx-auto flex w-full max-w-lg flex-col gap-6 pt-8">

                <header>
                    <h1 className="text-2xl font-semibold text-gray-900">
                        Edit Device
                    </h1>
                    <p className="mt-1 text-sm text-gray-600">
                        Update the device settings or delete this device.
                    </p>
                </header>

                <section className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
                    <div className="flex flex-col gap-5">

                        {/* Device ID */}
                        <div>
                            <label
                                htmlFor="device_id"
                                className="mb-2 block text-sm font-medium text-gray-700"
                            >
                                Device ID
                            </label>

                            <input
                                id="device_id"
                                type="text"
                                value={deviceID}
                                onChange={(event) => setID(event.target.value)}
                                required
                                className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                            />
                        </div>

                        {/* Device settings */}
                        <fieldset className="flex flex-col gap-4">
                            <legend className="mb-3 text-sm font-semibold text-gray-800">
                                Device settings
                            </legend>

                            <label
                                htmlFor="trusted"
                                className="flex cursor-pointer items-center justify-between gap-4"
                            >
                                <span className="text-sm text-gray-700">
                                    Trusted device
                                </span>
                                <input
                                    id="trusted"
                                    name="trusted"
                                    type="checkbox"
                                    checked={trusted}
                                    onChange={(event) => setTrusted(event.target.checked)}
                                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                />
                            </label>

                            <label
                                htmlFor="active"
                                className="flex cursor-pointer items-center justify-between gap-4"
                            >
                                <span className="text-sm text-gray-700">
                                    Active device
                                </span>
                                <input
                                    id="active"
                                    name="active"
                                    type="checkbox"
                                    checked={active}
                                    onChange={(event) => setActive(event.target.checked)}
                                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                />
                            </label>
                        </fieldset>

                        {/* Actions */}
                        <div className="flex flex-col gap-3 border-t border-gray-200 pt-5">
                            <button
                                type="button"
                                className="w-full rounded-md bg-blue-600 px-4 py-2.5 font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-gray-400"
                                onClick={() => saveChanges()}
                            >
                                Save changes
                            </button>

                            {!isDeleting && (
                                <button
                                    type="button"
                                    className="w-full rounded-md border border-red-300 bg-white px-4 py-2.5 font-medium text-red-600 hover:bg-red-50"
                                    onClick={() => setDeleting(true)}
                                >
                                    Delete device
                                </button>
                            )}

                            {isDeleting && (
                                <div className="flex flex-col gap-3 rounded-md border border-red-200 bg-red-50 p-4">
                                    <p className="text-sm font-medium text-red-800">
                                        Are you sure you want to delete this device?
                                    </p>

                                    <button
                                        type="button"
                                        className="w-full rounded-md border border-gray-300 bg-white px-4 py-2.5 font-medium text-gray-700 hover:bg-gray-50"
                                        onClick={() => setDeleting(false)}
                                    >
                                        Cancel deletion
                                    </button>

                                    <button
                                        type="button"
                                        className="w-full rounded-md bg-red-600 px-4 py-2.5 font-medium text-white hover:bg-red-700"
                                        onClick={() => deleteDevice()}
                                    >
                                        Confirm deletion
                                    </button>
                                </div>
                            )}
                        </div>

                    </div>
                </section>
            </div>
        </main>


    );
}