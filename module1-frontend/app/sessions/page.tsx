"use client";

import { type SessionStatus, type SessionType, SESSION_STATUSES } from "@/app/lib/types";
import { useEffect, useState, useMemo } from "react";
import { apiFetch, useAuth } from "@/app/components/AuthContext";
import { useFeedback } from "@/app/components/FeedbackContext";
import { useRouter } from "next/navigation";
import { formatDate, formatLocalToUTC } from '@/app/lib/utils';


type ActiveSession = {
    id: string,
    course_id: string,
    course_code: string,
    name: string,
    status: SessionStatus,
    scheduled_start: string,
    scheduled_end: string,
    checkin_opens_at: string,
    checkin_closes_at: string,
    venue_name: string
}

type InstructorSession = {
    id: string,
    course_id: string,
    course_code: string,
    course_name: string,
    instructor_id: string,
    name: string,
    session_type: SessionType,
    status: SessionStatus,
    scheduled_start: string,
    scheduled_end: string,
    checkin_opens_at: string,
    checkin_closes_at: string,
    venue_name: string,
    total_enrolled: number,
    checked_in_count: number
}

type MyFilters = {
    status: SessionStatus,
    upcoming: boolean,
    limit: number
}

type AllFilters = {
    status: SessionStatus,
    course_id: string,
    instructor_id: string,
    start_date: string,
    end_date: string,
    limit: number
    page_number: number
}

type AllResponse = {
    items: InstructorSession[],
    total: number,
    limit: number,
    offset: number
}

export default function SessionsPage() {

    const { setMsg } = useFeedback();
    const router = useRouter();
    const [search, setSearch] = useState('');
    const [loading, setLoading] = useState(false);
    const { isAuthenticated, user } = useAuth();
    const [sessionList, setSessionList] = useState<ActiveSession[]>([]);
    const [allResponse, setAllResponse] = useState<AllResponse>({ items: [], total: 0, limit: 0, offset: 0 });
    const [option, setOption] = useState<0 | 1 | 2>(0);
    const [myFilters, setMyFilters] = useState<MyFilters>({ status: "All statuses", upcoming: false, limit: 50 });
    const [allFilters, setAllFilters] =
        useState<AllFilters>({
            status: "All statuses",
            course_id: "",
            instructor_id: "",
            start_date: "",
            end_date: "",
            limit: 50,
            page_number: 1
        });

    async function fetchData(event: React.FormEvent<HTMLFormElement> | null) {

        if (event) {
            event.preventDefault();
        }

        setLoading(true);

        try {

            let response = null;

            if (option === 0) {
                response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/sessions/active`, {
                    method: 'GET'
                });
            }
            else if (option === 1) {
                const params = new URLSearchParams();

                if (myFilters.status !== 'All statuses') {
                    params.set('status', myFilters.status);
                }

                params.set('upcoming', String(myFilters.upcoming));
                params.set('limit', String(myFilters.limit));

                const query = params.toString();

                response = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/sessions/my-sessions?${query}`, {
                    method: 'GET'
                });
            }

            else if (option === 2) {

                const params = new URLSearchParams();

                if (myFilters.status !== 'All statuses') {
                    params.set('status', myFilters.status);
                }

                if (allFilters.course_id !== "")
                    params.set('course_id', allFilters.course_id);

                if (allFilters.instructor_id !== "")
                    params.set('instructor_id', allFilters.instructor_id);

                if (allFilters.start_date !== "") {
                    params.set('start_date', formatLocalToUTC(allFilters.start_date));
                }

                if (allFilters.end_date !== "") {
                    params.set('end_date', formatLocalToUTC(allFilters.end_date));
                }

                params.set('limit', String(allFilters.limit));

                params.set('offset', String((allFilters.page_number - 1) * allFilters.limit));

                const query = params.toString();

                response = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/sessions?${query}`, {
                    method: 'GET'
                });
            }

            const data = await response?.json();

            if (!response?.ok) {
                throw new Error("Error: " + (response?.status || "") + " " + (data.detail || "Request failed"));
            }

            if (option == 2) {
                setAllResponse(data as AllResponse);
            }
            else {
                setSessionList(data as ActiveSession[]);
            }

        } catch (error) {
            setMsg(error instanceof Error ? error.message : "Request failed", true);
        }

        setLoading(false);
    }

    useEffect(() => {

        fetchData(null);

    }, [isAuthenticated, user])

    const filteredSessions: InstructorSession[] | ActiveSession[] = useMemo<InstructorSession[] | ActiveSession[]>(() => {
        if (option === 2) {
            const query = search.trim().toLowerCase();

            if (!query) return allResponse.items;

            return allResponse.items.filter((session) =>
                [
                    session.name,
                    session.course_code,
                    session.status,
                    session.venue_name,

                ].some((value) => value?.toLowerCase().includes(query))
            );
        }
        else {
            const query = search.trim().toLowerCase();

            if (!query) return sessionList;

            return sessionList.filter((session) =>
                [
                    session.name,
                    session.course_code,
                    session.status,
                    session.venue_name,

                ].some((value) => value?.toLowerCase().includes(query))
            );
        }
    }, [sessionList, allResponse, search, option]);


    return (
        <main className="mx-auto flex h-[calc(100vh-4rem)] max-w-5xl flex-col gap-5 p-4 sm:p-6">
            <header>
                <h1 className="text-3xl font-bold text-gray-900">
                    Sessions
                </h1>
                <p className="mt-1 text-sm text-gray-500">
                    Browse available sessions and their check-in times.
                </p>
            </header>

            {/* My Sessions query form */}
            {isAuthenticated() && option == 1 && (
                <form
                    onSubmit={fetchData}
                    className="shrink-0 space-y-4 rounded-xl border border-gray-200 bg-white p-4">
                    <h2 className="font-semibold text-gray-900">
                        Filter My Sessions
                    </h2>

                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                        <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                            Status
                            <select
                                value={myFilters.status}
                                onChange={(event) =>
                                    setMyFilters((prev) => ({
                                        ...prev,
                                        status: event.target.value as SessionStatus,
                                    }))
                                }
                                className="rounded-lg border border-gray-300 p-2">
                                {SESSION_STATUSES.map((status) => (
                                    <option key={status} value={status}>
                                        {status}
                                    </option>
                                ))}
                            </select>
                        </label>

                        <label className="flex items-center gap-2 self-end pb-2 text-sm text-gray-700">
                            <input
                                type="checkbox"
                                checked={myFilters.upcoming}
                                onChange={(event) =>
                                    setMyFilters((prev) => ({
                                        ...prev,
                                        upcoming: event.target.checked,
                                    }))
                                }
                                className="h-4 w-4 rounded"
                            />
                            Upcoming only
                        </label>

                        <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                            Limit
                            <input
                                type="number"
                                min={1}
                                max={500}
                                required
                                value={myFilters.limit}
                                onChange={(event) =>
                                    setMyFilters((prev) => ({
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
            )}

            {/* Search All query form */}
            {isAuthenticated() && option == 2 && (
                <form
                    onSubmit={fetchData}
                    className="shrink-0 space-y-4 rounded-xl border border-gray-200 bg-white p-4">
                    <h2 className="font-semibold text-gray-900">
                        Search All Sessions
                    </h2>

                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                        <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                            Status
                            <select
                                value={allFilters.status}
                                onChange={(event) =>
                                    setAllFilters((prev) => ({
                                        ...prev,
                                        status: event.target.value as SessionStatus,
                                    }))
                                }
                                className="rounded-lg border border-gray-300 p-2">
                                {SESSION_STATUSES.map((status) => (
                                    <option key={status} value={status}>
                                        {status}
                                    </option>
                                ))}
                            </select>
                        </label>

                        <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                            Course ID
                            <input
                                type="text"
                                value={allFilters.course_id}
                                onChange={(event) =>
                                    setAllFilters((prev) => ({
                                        ...prev,
                                        courseId: event.target.value,
                                    }))
                                }
                                placeholder="Enter course ID"
                                className="rounded-lg border border-gray-300 p-2"
                            />
                        </label>

                        <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                            Instructor ID
                            <input
                                type="text"
                                value={allFilters.instructor_id}
                                onChange={(event) =>
                                    setAllFilters((prev) => ({
                                        ...prev,
                                        instructorId: event.target.value,
                                    }))
                                }
                                placeholder="Enter instructor ID"
                                className="rounded-lg border border-gray-300 p-2"
                            />
                        </label>

                        <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                            Start date
                            <input
                                type="datetime-local"
                                value={allFilters.start_date}
                                onChange={(event) =>
                                    setAllFilters((prev) => ({
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
                                value={allFilters.end_date}
                                min={allFilters.start_date || undefined}
                                onChange={(event) =>
                                    setAllFilters((prev) => ({
                                        ...prev,
                                        end_date: event.target.value,
                                    }))
                                }
                                className="rounded-lg border border-gray-300 p-2"
                            />
                        </label>

                        <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                            Limit
                            <input
                                type="number"
                                min={1}
                                max={500}
                                required
                                value={allFilters.limit}
                                onChange={(event) =>
                                    setAllFilters((prev) => ({
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

                        <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                            Page number
                            <input
                                type="number"
                                min={1}
                                required
                                value={allFilters.page_number}
                                onChange={(event) =>
                                    setAllFilters((prev) => ({
                                        ...prev,
                                        pageNumber: Math.max(
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
            )}

            {/* View selector: only show it for authenticated roles */}
            {isAuthenticated() && (
                <div
                    className="flex shrink-0 flex-wrap gap-2"
                    role="group"
                    aria-label="Session view">
                    <button
                        type="button"
                        onClick={() => setOption(0)}
                        aria-pressed={option === 0}
                        className={`rounded-lg px-4 py-2 text-sm font-medium ${option === 0
                            ? 'bg-blue-600 text-white'
                            : 'border border-gray-300 bg-white text-gray-700 hover:bg-gray-50'}`}>
                        Active sessions
                    </button>


                    <button
                        type="button"
                        onClick={() => setOption(1)}
                        aria-pressed={option === 1}
                        className={`rounded-lg px-4 py-2 text-sm font-medium ${option === 1
                            ? 'bg-blue-600 text-white'
                            : 'border border-gray-300 bg-white text-gray-700 hover:bg-gray-50'}`}>
                        My sessions
                    </button>


                    {user?.role === "instructor" || user?.role === "admin" && (
                        <button
                            type="button"
                            onClick={() => setOption(2)}
                            aria-pressed={option === 2}
                            className={`rounded-lg px-4 py-2 text-sm font-medium ${option === 2
                                ? 'bg-blue-600 text-white'
                                : 'border border-gray-300 bg-white text-gray-700 hover:bg-gray-50'}`}>
                            Search all
                        </button>
                    )}
                </div>
            )}

            {/* Search bar */}
            <div className="shrink-0">
                <label htmlFor="session-search" className="sr-only">
                    Search sessions
                </label>
                <input
                    id="session-search"
                    type="search"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search by name, course code, status, or venue..."
                    className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3
                    text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"/>
            </div>

            {/* Scrollable session list */}
            <section
                aria-label="Session results"
                aria-busy={loading}
                className="min-h-0 flex-1 overflow-y-auto rounded-xl"
            >
                {loading ? (
                    <p className="py-8 text-center text-gray-500">
                        Loading sessions...
                    </p>
                ) : filteredSessions.length === 0 ? (
                    <p className="py-8 text-center text-gray-500">
                        {(option !== 2) ? sessionList.length === 0 ? 'No sessions found.' : 'No sessions match your search.'
                            : allResponse.items.length === 0 ? 'No sessions found.' : 'No sessions match your search.'}
                    </p>
                ) : (
                    <div className="space-y-3 pb-4">
                        {filteredSessions.map((session) => (
                            <button
                                key={session.id}
                                type="button"
                                disabled={!isAuthenticated()}
                                onClick={() => router.push(`/sessions/details?id=${encodeURIComponent(session.id)}`)}
                                className="block w-full rounded-xl border border-gray-200 bg-white p-4 disabled:cursor-not-allowed
                                text-left shadow-sm transition hover:border-blue-300 hover:shadow-md
                                focus:outline-none focus:ring-2 focus:ring-blue-500">

                                <div className="flex flex-wrap items-start justify-between gap-3">
                                    <div className="min-w-0">
                                        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                                            {session.course_code}
                                        </p>
                                        <h2 className="mt-1 text-lg font-semibold text-gray-900">
                                            {session.name}
                                        </h2>
                                    </div>

                                    <span
                                        className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${session.status === 'active'
                                            ? 'bg-green-100 text-green-800'
                                            : session.status === 'closed'
                                                ? 'bg-gray-100 text-gray-700'
                                                : session.status === 'cancelled'
                                                    ? 'bg-red-100 text-red-800'
                                                    : 'bg-blue-100 text-blue-800'}`}>
                                        {session.status}
                                    </span>
                                </div>

                                <div className="mt-3 space-y-2 text-sm text-gray-600">
                                    <p>
                                        <span className="font-medium text-gray-800">
                                            Venue:
                                        </span>{' '}
                                        {session.venue_name || 'Not specified'}
                                    </p>

                                    <p>
                                        <span className="font-medium text-gray-800">
                                            Scheduled:
                                        </span>{' '}
                                        {formatDate(session.scheduled_start)}
                                        {' – '}
                                        {formatDate(session.scheduled_end)}
                                    </p>

                                    <p>
                                        <span className="font-medium text-gray-800">
                                            Check-in window:
                                        </span>{' '}
                                        {formatDate(session.checkin_opens_at)}
                                        {' – '}
                                        {formatDate(session.checkin_closes_at)}
                                    </p>

                                    {option === 2 && ('total_enrolled' in session) && (

                                        <p>
                                            <span className="font-medium text-gray-800">
                                                Checked-in:
                                            </span>{' '}
                                            {session.checked_in_count}/{session.total_enrolled}
                                        </p>

                                    )}


                                </div>
                            </button>
                        ))}
                    </div>
                )}
            </section>

            <p className="shrink-0 text-xs text-gray-500">
                Showing {filteredSessions.length} of {(option === 2) ? (allResponse.total + ` (limit: ${allResponse.limit})`) : sessionList.length} sessions
            </p>

        </main>
    );
}