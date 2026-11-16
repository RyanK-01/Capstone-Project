"use client";

import { useRouter } from "next/navigation";
import { useState, useEffect } from 'react';
import { apiFetch, useAuth } from '@/app/components/AuthContext';
import { useFeedback } from '@/app/components/FeedbackContext'
import { formatDate } from '@/app/lib/utils';


type Profile = {
    id: string;
    email: string;
    full_name: string;
    role: string;
    camera_consent: boolean;
    geolocation_consent: boolean;
    face_enrolled: boolean;
    created_at: string;
};

export default function ProfilePage() {

    const [profile, setProfile] = useState<Profile | null>(null);
    const [editProfile, setEditProfile] = useState<Profile | null>(null);
    const [isEditing, setEditing] = useState(false);
    const { isAuthenticated } = useAuth();
    const { setMsg } = useFeedback();

    const router = useRouter();

    const fetchData = async () => {

        try {
            const response = await apiFetch(
                `${process.env.NEXT_PUBLIC_API_BASE_URL}/users/me`,
                { method: 'GET' }
            );
            const responseProfile = await response.json() as Profile;

            setProfile(responseProfile);
            setEditProfile(responseProfile);

        } catch {
            setMsg("Profile failed to load", true);
            setProfile(null);
            setEditProfile(null);
        }

    }

    useEffect(() => {
        fetchData();
    }, [isAuthenticated]);


    async function submit() {
        try {

            const saveChanges = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/users/me`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(editProfile)
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
            setEditing(false);
            fetchData();

        } catch {
            setMsg("Changes failed to save", true);
            setEditProfile(profile);
            console.error('Changes failed to save');
        }
    }

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
        <main className="flex flex-col min-h-screen min-w-screen bg-white p-4 items-center">

            <div className="flex flex-col w-full max-w-4xl rounded-2xl border border-gray-200 bg-white p-4">

                <h1 className="text-4xl font-bold mb-8 w-full items-center justify-center text-center">
                    <input type="text" id="name" name="name" disabled={!isEditing}
                        value={editProfile ? editProfile.full_name : "Something went wrong... 🧐"}
                        onChange={(event) => setEditProfile((prev) => prev ? { ...prev, full_name: event.target.value } : null)}
                        className="w-full bg-white text-center rounded-md enabled:border enabled:border-gray-300 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500">
                    </input>
                </h1>

                <div className="mt-3 space-y-2 text-sm text-gray-600">
                    <p>
                        <span className="font-medium text-gray-800">
                            ID:
                        </span>{' '}
                        {profile?.id}
                    </p>
                    <p>
                        <span className="font-medium text-gray-800">
                            Email:
                        </span>{' '}
                        {profile?.email}
                    </p>
                    <p>
                        <span className="font-medium text-gray-800">
                            Role:
                        </span>{' '}
                        {profile?.role}
                    </p>
                    <p>
                        <span className="font-medium text-gray-800">
                            Camera consent:
                        </span>{' '}
                        <input type="checkbox" id="camera" name="camera" checked={editProfile ? editProfile.camera_consent : false} disabled={!isEditing}
                            onChange={(event) => setEditProfile((prev) => prev ? { ...prev, camera_consent: event.target.checked } : null)}
                            className="h-4 w-4 rounded">
                        </input>
                    </p>
                    <p>
                        <span className="font-medium text-gray-800">
                            Geolocation consent:
                        </span>{' '}
                        <input type="checkbox" id="geolocation" name="geolocation" checked={editProfile ? editProfile.geolocation_consent : false} disabled={!isEditing}
                            onChange={(event) => setEditProfile((prev) => prev ? { ...prev, geolocation_consent: event.target.checked } : null)}
                            className="h-4 w-4 rounded">
                        </input>
                    </p>
                    <p>
                        <span className="font-medium text-gray-800">
                            Face enrolled:
                        </span>{' '}
                        {String(profile?.face_enrolled)}
                    </p>
                    <p>
                        <span className="font-medium text-gray-800">
                            Created at:
                        </span>{' '}
                        {formatDate(profile?.created_at || "1970-01-01T00:00:00Z")}
                    </p>
                </div>

                <div className="flex flex-row justify-evenly mt-8">

                    {!isEditing && !profile?.face_enrolled && (
                        <button className="text-md max-h-full text-center p-4 font-bold shadow-2xl 
            rounded-lg bg-blue-500 hover:bg-blue-700 text-white disabled:bg-gray-400"
                            type="button" onClick={() => {
                                setMsg("", true);
                                router.push('/enroll-face');
                            }}>
                            Enroll face
                        </button>
                    )}

                    {!isEditing && (
                        <button className="text-md max-h-full min-w-32 text-center p-4 font-bold shadow-2xl 
            rounded-lg bg-blue-500 hover:bg-blue-700 text-white disabled:bg-gray-400"
                            type="button" onClick={() => {
                                setEditing(true);
                                setMsg("", true);
                            }}>
                            Edit
                        </button>
                    )}

                    {isEditing && (
                        <button className="text-md w-1/3 text-center p-4 font-bold shadow-2xl rounded-lg bg-blue-500 hover:bg-blue-700 text-white"
                            type="button" onClick={() => {
                                setEditing(false);
                                setEditProfile(profile);
                            }}>
                            Cancel
                        </button>
                    )}

                    {isEditing && (
                        <button className="text-md w-1/3 text-center p-4 font-bold shadow-2xl rounded-lg bg-blue-500 hover:bg-blue-700 text-white disabled:bg-gray-400"
                            type="button" onClick={() => {
                                submit();
                            }}>
                            Save changes
                        </button>
                    )}
                </div>
            </div>

        </main>
    );
}