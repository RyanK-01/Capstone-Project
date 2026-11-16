"use client";

import { CHECKIN_STATUSES, type CheckinStatus } from "@/app/lib/types";
import { apiFetch, useAuth } from "../components/AuthContext";
import { useEffect, useState, useMemo } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useFeedback } from "../components/FeedbackContext";
import { formatDate, formatLocalToUTC } from "../lib/utils";

type Filters = {
    session_id: string,
    course_id: string,
    student_id: string,
    status: CheckinStatus,
    min_risk_score: number,
    max_risk_score: number,
    start_date: string,
    end_date: string,
    limit: number,
    page_number: number
}

type DisplayInfoStudent = {
    id: string
    course_code: string,
    session_name: string,
    checked_in_at: string
    status: CheckinStatus,
}

type DisplayInfoTA = {
    id: string
    session_name: string,
    student_name: string
    checked_in_at: string
    status: CheckinStatus,
}

export default function CheckinsPage() {

    const { user, isAuthenticated } = useAuth();
    const searchParams = useSearchParams();
    const [flagged, setFlagged] = useState(user?.role === "ta");
    const [TAList, setTAList] = useState<DisplayInfoTA[]>([]);
    const [studentList, setStudentList] = useState<DisplayInfoStudent[]>([]);
    const { setMsg } = useFeedback();
    const router = useRouter();
    const [loading, setLoading] = useState(false);
    const [search, setSearch] = useState("");
    const [filters, setFilters] = useState<Filters>({
        session_id: "",
        course_id: "",
        student_id: "",
        status: "All statuses",
        min_risk_score: 0,
        max_risk_score: 0,
        start_date: "",
        end_date: "",
        limit: 50,
        page_number: 1
    });
    const [sessionID, setSessionID] = useState(searchParams.get('session-id'));
    const sessionName = searchParams.get('session-name');

    const fetchCheckinsForSession = async () => {
        setLoading(true);
        try {

            const response = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/checkins/session/` + sessionID, {
                method: 'GET'
            })

            const data = await response.json();

            if (!response.ok) {
                throw new Error(`(${response.status}): ${data.detail ?? "Unable to load checkins"}`)
            }

            setTAList(data as DisplayInfoTA[]);

        } catch (error) {
            setMsg((error instanceof Error) ? error.message : "Unable to load checkins", true);
        }
        setLoading(false);

    }

    const fetchMyCheckins = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();

            if (filters.course_id !== "") {
                params.set('course_id', filters.course_id);
            }

            params.set('limit', String(filters.limit));

            const query = params.toString();

            const response = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/checkins/my-checkins?${query}`, {
                method: 'GET'
            })

            const data = await response.json();

            if (!response.ok) {
                throw new Error(`(${response.status}): ${data.detail ?? "Unable to load checkins"}`)
            }

            setStudentList(data as DisplayInfoStudent[]);

        } catch (error) {
            setMsg((error instanceof Error) ? error.message : "Unable to load checkins", true);
        }
        setLoading(false);
    }

    const fetchFlaggedCheckins = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();

            if (filters.course_id !== "") {
                params.set('course_id', filters.course_id);
            }

            if (filters.session_id !== "") {
                params.set('session_id', filters.session_id);
            }

            params.set('limit', String(filters.limit));

            const query = params.toString();

            const response = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/checkins/flagged?${query}`, {
                method: 'GET'
            })

            const data = await response.json();

            if (!response.ok) {
                throw new Error(`(${response.status}): ${data.detail ?? "Unable to load checkins"}`)
            }

            setTAList(data as DisplayInfoTA[]);

        } catch (error) {
            setMsg((error instanceof Error) ? error.message : "Unable to load checkins", true);
        }
        setLoading(false);
    }

    const fetchInstructorCheckins = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();

            if (filters.course_id !== "") {
                params.set('course_id', filters.course_id);
            }

            if (filters.session_id !== "") {
                params.set('session_id', filters.session_id);
            }

            if (filters.status !== "All statuses") {
                params.set('status', filters.status);
            }

            if (filters.min_risk_score >= 0) {
                params.set('min_risk_score', String(filters.min_risk_score));
            }

            if (filters.max_risk_score >= 0) {
                params.set('max_risk_score', String(filters.max_risk_score));
            }

            if (filters.session_id !== "") {
                params.set('session_id', filters.session_id);
            }

            if (filters.start_date !== "") {
                params.set('start_date', formatLocalToUTC(filters.start_date));
            }

            if (filters.end_date !== "") {
                params.set('end_date', formatLocalToUTC(filters.end_date));
            }

            params.set('limit', String(filters.limit));

            params.set('offset', String((filters.page_number - 1) * filters.limit));

            const query = params.toString();

            const response = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/checkins?${query}`, {
                method: 'GET'
            })

            const data = await response.json();

            if (!response.ok) {
                throw new Error(`(${response.status}): ${data.detail ?? "Unable to load checkins"}`)
            }

            setTAList(data.items as DisplayInfoTA[]);

        } catch (error) {
            setMsg((error instanceof Error) ? error.message : "Unable to load checkins", true);
        }
        setLoading(false);
    }

    useEffect(() => {
        if (!isAuthenticated())
            return;

        if (sessionID) {
            if (user?.role !== 'student') {
                fetchCheckinsForSession();
            }
            return;
        }

        if (user?.role === 'student') {
            fetchMyCheckins();
            return;
        }


    }, [isAuthenticated()])


    function submit(event: React.FormEvent<HTMLFormElement>) {
        setSessionID("");
        event.preventDefault();

        if (user?.role === "student") {
            fetchMyCheckins();
        }
        else if (flagged) {
            fetchFlaggedCheckins();
        }
        else if (user?.role === "admin" || user?.role === "instructor") {
            fetchInstructorCheckins();
        }
    }

    const filteredCheckins: DisplayInfoTA[] | DisplayInfoStudent[] = useMemo<DisplayInfoTA[] | DisplayInfoStudent[]>(() => {

        const query = search.trim().toLowerCase();

        if (user?.role === "student") {

            console.log(studentList);

            if (!query) return studentList;

            return studentList.filter((checkin) =>
                [
                    checkin.session_name,
                    checkin.status,
                    checkin.course_code

                ].some((value) => value?.toLowerCase().includes(query))
            );
        }
        else {
            
            if (!query) return TAList;

            return TAList.filter((checkin) =>
                [
                    checkin.session_name,
                    checkin.status,
                    checkin.student_name

                ].some((value) => value?.toLowerCase().includes(query))
            );
        }

    }, [studentList, TAList, search]);

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
        <main className="mx-auto flex h-[calc(100vh-4rem)] max-w-5xl flex-col gap-5 p-4 sm:p-6">
            <header>
                <h1 className="text-3xl font-bold text-gray-900">
                    Checkins
                </h1>
                <p className="mt-1 text-sm text-gray-500">
                    {user?.role === "student" ? "View your checkin history." : 
                    sessionID !== "" && sessionName !== null ? `View checkins for session "${sessionName}"` :
                    `View ${flagged ? "flagged/appealed" : ""} checkins submitted by students.`}
                </p>
            </header>

  
            <form
                onSubmit={submit}
                className="shrink-0 space-y-4 rounded-xl border border-gray-200 bg-white p-4">
                <h2 className="font-semibold text-gray-900">
                    Filter Checkins
                </h2>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">

                    <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                        Course ID
                        <input
                            type="text"
                            value={filters.course_id}
                            onChange={(event) =>
                                setFilters((prev) => ({
                                    ...prev,
                                    course_id: event.target.value,
                                }))
                            }
                            placeholder="Enter course ID"
                            className="rounded-lg border border-gray-300 p-2"
                        />
                    </label>

                    {user?.role !== "student" && (
                        <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                            Session ID
                            <input
                                type="text"
                                value={filters.session_id}
                                onChange={(event) =>
                                    setFilters((prev) => ({
                                        ...prev,
                                        session_id: event.target.value,
                                    }))
                                }
                                placeholder="Enter session ID"
                                className="rounded-lg border border-gray-300 p-2"
                            />
                        </label>
                    )}

                    {!flagged && (user?.role === "admin" || user?.role !== "instructor") && (
                        <>
                            <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                                Student ID
                                <input
                                    type="text"
                                    value={filters.student_id}
                                    onChange={(event) =>
                                        setFilters((prev) => ({
                                            ...prev,
                                            student_id: event.target.value,
                                        }))
                                    }
                                    placeholder="Enter student ID"
                                    className="rounded-lg border border-gray-300 p-2"
                                />
                            </label>

                            <label className="flex capitalize flex-col gap-1 text-sm font-medium text-gray-700">
                                Status
                                <select
                                    value={filters.status}
                                    onChange={(event) =>
                                        setFilters((prev) => ({
                                            ...prev,
                                            status: event.target.value as CheckinStatus,
                                        }))
                                    }
                                    className="rounded-lg capitalize border border-gray-300 p-2">
                                    {CHECKIN_STATUSES.map((status) => (
                                        <option key={status} value={status}>
                                            {status}
                                        </option>
                                    ))}
                                </select>
                            </label>

                            <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                                Min risk score
                                <input
                                    step="any"
                                    type="number"
                                    min={0.0}
                                    max={1.0}
                                    required
                                    value={filters.min_risk_score}
                                    onChange={(event) =>
                                        setFilters((prev) => ({
                                            ...prev,
                                            min_risk_score: Math.max(0.0, Number(event.target.value) || 0.0),
                                        }))
                                    }
                                    className="rounded-lg border border-gray-300 p-2"
                                />
                            </label>

                            <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                                Max risk score
                                <input
                                    step="any"
                                    type="number"
                                    min={0.0}
                                    max={1.0}
                                    required
                                    value={filters.max_risk_score}
                                    onChange={(event) =>
                                        setFilters((prev) => ({
                                            ...prev,
                                            max_risk_score: Math.max(0.0, Number(event.target.value) || 0.0),
                                        }))
                                    }
                                    className="rounded-lg border border-gray-300 p-2"
                                />
                            </label>

                            <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                                Start date
                                <input
                                    type="datetime-local"
                                    value={filters.start_date}
                                    onChange={(event) =>
                                        setFilters((prev) => ({
                                            ...prev,
                                            start_date: event.target.value,
                                        }))
                                    }
                                    className="rounded-lg border border-gray-300 p-2"
                                />
                            </label>
                            <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                                End date
                                <input
                                    type="datetime-local"
                                    value={filters.end_date}
                                    onChange={(event) =>
                                        setFilters((prev) => ({
                                            ...prev,
                                            end_date: event.target.value,
                                        }))
                                    }
                                    className="rounded-lg border border-gray-300 p-2"
                                />
                            </label>
                            <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                                Page number
                                <input
                                    type="number"
                                    min={1}
                                    required
                                    value={filters.page_number}
                                    onChange={(event) =>
                                        setFilters((prev) => ({
                                            ...prev,
                                            page_number: Math.max(
                                                1,
                                                Number(event.target.value) || 1
                                            ),
                                        }))
                                    }
                                    className="rounded-lg border border-gray-300 p-2"
                                />
                            </label>
                        </>
                    )}

                    {(user?.role === "instructor" || user?.role === "admin") && (
                        <label className="flex items-center gap-2 self-end pb-2 text-sm text-gray-700">
                            <input
                                type="checkbox"
                                checked={flagged}
                                onChange={(event) => setFlagged(event.target.checked)}
                                className="h-4 w-4 rounded"
                            />
                            Flagged/appealed only
                        </label>
                    )}

                    <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                        Limit
                        <input
                            type="number"
                            min={1}
                            max={500}
                            required
                            value={filters.limit}
                            onChange={(event) =>
                                setFilters((prev) => ({
                                    ...prev,
                                    limit: Math.max(
                                        1,
                                        Number(event.target.value) || 1
                                    ),
                                }))
                            }
                            className="rounded-lg border border-gray-300 p-2"
                        />
                    </label>
                </div>

                <button
                    type="submit"
                    disabled={loading}
                    className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
                    Apply filters
                </button>
            </form>

      
            <div className="shrink-0">
                <label htmlFor="session-search" className="sr-only">
                    Search sessions
                </label>
                <input
                    id="session-search"
                    type="search"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search"
                    className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3
                    text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"/>
            </div>

            
            <section
                aria-label="Session results"
                aria-busy={loading}
                className="min-h-0 flex-1 overflow-y-auto rounded-xl">
                {loading ? (
                    <p className="py-8 text-center text-gray-500">
                        Loading checkins...
                    </p>
                ) : filteredCheckins.length === 0 ? (
                    <p className="py-8 text-center text-gray-500">
                        {(studentList.length === 0 && TAList.length === 0) ? 'No checkins found.' : 'No checkins match your search.'}
                    </p>
                ) : (
                    <div className="space-y-3 pb-4">
                        {(filteredCheckins).map((checkin) => (
                            <button
                                key={checkin.id}
                                type="button"
                                onClick={() => router.push(`/checkins/details?id=${encodeURIComponent(checkin.id)}`)}
                                className="block w-full rounded-xl border border-gray-200 bg-white p-4 disabled:cursor-not-allowed
                                text-left shadow-sm transition hover:border-blue-300 hover:shadow-md
                                focus:outline-none focus:ring-2 focus:ring-blue-500">

                                <div className="flex flex-wrap items-start justify-between gap-3">
                                    <div className="min-w-0">

                                        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                                            {'course_code' in checkin ? checkin.course_code : checkin.student_name}
                                        </p>
                                        <h2 className="mt-1 text-lg font-semibold text-gray-900">
                                            {checkin.session_name}
                                        </h2>
                                    </div>

                                    <span
                                        className={`shrink-0 capitalize rounded-full px-3 py-1 text-xs font-semibold ${checkin.status === 'approved'
                                            ? 'bg-green-100 text-green-800'
                                            : checkin.status === 'pending'
                                                ? 'bg-blue-100 text-blue-700'
                                                : (checkin.status === 'flagged' || checkin.status === 'appealed')
                                                    ? 'bg-orange-100 text-orange-500'
                                                    : 'bg-red-100 text-red-800'}`}>
                                        {checkin.status}
                                    </span>
                                </div>

                                <div className="mt-3 space-y-2 text-sm text-gray-600">

                                    <p>
                                        <span className="font-medium text-gray-800">
                                            Checked in at:
                                        </span>{' '}
                                        {formatDate(checkin.checked_in_at)}
                                    </p>

                                </div>
                            </button>
                        ))}
                    </div>
                )}
            </section>

            <p className="shrink-0 text-xs text-gray-500">
                Showing {filteredCheckins.length} of {Math.max(studentList.length, TAList.length)} sessions
            </p>

        </main>
    );
}