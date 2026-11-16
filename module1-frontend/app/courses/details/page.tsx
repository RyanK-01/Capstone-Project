"use client";

import { useFeedback } from '@/app/components/FeedbackContext';
import { useAuth, apiFetch } from '@/app/components/AuthContext';
import { useRouter, useSearchParams } from 'next/navigation';
import { useState, useEffect } from 'react';

type Course = {
    id: string,
    code: string,
    name: string,
    description: string | null,
    semester: string,
    is_active: boolean,
    venue_latitude: number | null,
    venue_longitude: number | null,
    venue_name: string | null,
    geofence_radius_meters: number,
    require_face_recognition: boolean,
    require_device_binding: boolean,
    risk_threshold: number,
    created_at: string,
    updated_at: string

}

type EditDetails = {
  name: string,
  venue_name: string,
  risk_threshold: number
}

export default function CourseDetailsPage() {

    const [course, setCourse] = useState<Course | null>(null);
    const [editDetails, setEditDetails] = useState<EditDetails | null>(null);
    const { setMsg } = useFeedback();
    const { isAuthenticated, user } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();
    const [isEditing, setEditing] = useState(false);
    const [deleteCourse, setDelete] = useState(false);


    const id = searchParams.get('id');

    async function fetchData() {

        try {

            if (!id) {
                throw new Error("Invalid session ID");
            }

            const response = await apiFetch(
                `${process.env.NEXT_PUBLIC_API_BASE_URL}/courses/${id}`,
                { method: 'GET' }
            );

            if (!response.ok) {
                const data = await response.json();
                let altMessage = "Request failed";

                switch (response.status) {
                    case 401: {
                        altMessage = "Invalid credentials";
                        break;
                    }
                    case 403: {
                        altMessage = "Account disabled";
                        break;
                    }
                    case 404: {
                        altMessage = "Course could not be found";
                        break;
                    }
                    default: {
                        altMessage = "Request failed (" + response.status + ")";
                    }
                }
                throw new Error(data.detail || altMessage);
            }

            const data = await response.json();
            setMsg("", true);
            setCourse(data as Course);
            setEditDetails(data as EditDetails);

        }
        catch (error) {

            setMsg(error instanceof Error ? error.message : "Course details failed to load", true);
            setCourse(null);
            setEditDetails(null);

        }

    }

    useEffect(() => {
        fetchData();
    }, [])

    async function submit() {
        try {

            let saveChanges = null;

            if (deleteCourse) {
                saveChanges = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/courses/` + course?.id, {
                    method: 'DELETE',
                });
            }
            else {
                saveChanges = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/sessions/` + course?.id, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(editDetails)
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

            if (deleteCourse) {
                router.push("/sessions");
            }
            else {
                fetchData();
            }
            setEditing(false);
        } catch {
            setMsg("Changes failed to save", true);
            console.error('Changes failed to save');
        }

    }

    return (

        <main className="min-h-screen w-full bg-gray-50 px-4 py-8 sm:px-6 lg:px-8">
            <div className="mx-auto max-w-6xl space-y-8">

                {/* Course header */}
                <header className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm sm:p-8">
                    <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
                        <div className="min-w-0 flex-1">
                            <p className="mb-2 text-sm font-medium uppercase tracking-wider text-gray-500">
                                Course details
                            </p>

                            <p className="mt-2 break-all text-sm text-gray-500">
                                {course?.code ?? "—"}
                            </p>

                            <input
                                type="text"
                                id="name"
                                name="name"
                                disabled={!isEditing}
                                value={editDetails?.name ?? ""}
                                onChange={(event) =>
                                    setEditDetails((prev) =>
                                        prev ? { ...prev, name: event.target.value } : null
                                    )
                                }
                                aria-label="Session name"
                                className="w-full rounded-lg border border-transparent bg-transparent px-2 py-1 text-2xl font-bold text-gray-900 transition
                                    enabled:border-gray-300 enabled:bg-gray-50
                                    enabled:hover:border-gray-400
                                    focus:outline-none focus:ring-2 focus:ring-blue-500
                                    disabled:cursor-default disabled:opacity-100
                                    sm:text-3xl"/>

                            <p className="mt-2 break-all text-sm text-gray-500">
                                Course ID: {course?.id ?? "—"}
                            </p>
                        </div>
                    </div>
                </header>
            </div>
        </main>

    );
}