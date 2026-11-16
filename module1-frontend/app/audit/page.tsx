"use client";

import { useMemo, useState } from 'react';
import { formatLocalToUTC } from '../lib/utils';
import { apiFetch, useAuth } from '../components/AuthContext';
import { useFeedback } from '@/app/components/FeedbackContext'

type Filter = {
    user_id: string,
    action: string,
    resource_id: string,
    resource_type: string,
    success: "" | "true" | "false",
    start_date: string,
    end_date: string,
    limit: number,
    page_number: number
}

type Audit = {
    id: string,
    user_id: string,
    user_email: string,
    action: string,
    resource_type: string,
    resource_id: string,
    ip_address: string,
    user_agent: string,
    device_id: string,
    details: string,
    success: true,
    timestamp: string
}

export default function AuditPage() {

    const { setMsg } = useFeedback();
    const [total, setTotal] = useState(0);
    const { user } = useAuth();
    const [auditList, setAuditList] = useState<Audit[]>([]);
    const [search, setSearch] = useState("");
    const [loading, setLoading] = useState(false);
    const [expandedLogs, setExpandedLogs] = useState<Set<string>>(new Set());
    const [filters, setFilters] = useState<Filter>({
        user_id: "",
        action: "",
        resource_id: "",
        resource_type: "",
        success: "",
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

            const params = new URLSearchParams();

            if (filters.user_id !== "") {
                params.set('user_id', filters.user_id);
            }

            if (filters.action !== "") {
                params.set('action', filters.action);
            }

            if (filters.resource_type !== "") {
                params.set('resource_type', filters.resource_type);
            }

            if (filters.resource_id !== "") {
                params.set('resource_id', filters.resource_id);
            }

            if (filters.success !== "") {
                params.set('success', filters.success);
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

            const response = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/audit?${query}`, {
                method: 'GET'
            });

            const data = await response?.json();

            if (!response?.ok) {
                throw new Error("Error: " + (response?.status || "") + " " + (data.detail || "Request failed"));
            }


            setAuditList(data.items as Audit[]);
            setTotal(data.total);


        } catch (error) {
            setMsg(error instanceof Error ? error.message : "Request failed", true);
        }

        setLoading(false);

    }

    const filteredLogs = useMemo<Audit[]>(() => {

        const query = search.trim().toLowerCase();

        if (!query) return auditList;

        return auditList.filter((audit) =>
            [
                audit.ip_address,
                audit.user_email,
                audit.user_agent,


            ].some((value) => value?.toLowerCase().includes(query))
        );

    }, [auditList, search]);

    if (!user || user.role !== "admin") {
        return (
            <main className="flex min-h-screen flex-col items-center justify-center bg-gray-100">

                <div className="flex w-full mb-4 flex-row justify-evenly mt-auto">
                    <h1 className="text-4xl font-bold w-full text-center text-white m-8">
                        You need to be logged in as administrator to access this page
                    </h1>
                </div>

            </main>
        );
    }

    return (
        <main className="mx-auto flex h-[calc(100vh-4rem)] max-w-5xl flex-col gap-5 p-4 sm:p-6">
            <header>
                <h1 className="text-3xl font-bold text-gray-900">
                    Audit
                </h1>
                <p className="mt-1 text-sm text-gray-500">
                    Browse audit logs.
                </p>
            </header>

            <form
                onSubmit={fetchData}
                className="shrink-0 space-y-4 rounded-xl border border-gray-200 bg-white p-4">
                <h2 className="font-semibold text-gray-900">
                    Filter logs.
                </h2>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">

                    <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                        User ID
                        <input
                            type="text"
                            value={filters.user_id}
                            onChange={(event) =>
                                setFilters((prev) => ({
                                    ...prev,
                                    user_id: event.target.value,
                                }))
                            }
                            placeholder="Enter user ID"
                            className="rounded-lg border border-gray-300 p-2"
                        />
                    </label>

                    <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                        Action type
                        <input
                            type="text"
                            value={filters.action}
                            onChange={(event) =>
                                setFilters((prev) => ({
                                    ...prev,
                                    action: event.target.value,
                                }))
                            }
                            placeholder="Enter action type"
                            className="rounded-lg border border-gray-300 p-2"
                        />
                    </label>


                    <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                        Resource type
                        <input
                            type="text"
                            value={filters.resource_type}
                            onChange={(event) =>
                                setFilters((prev) => ({
                                    ...prev,
                                    resource_type: event.target.value,
                                }))
                            }
                            placeholder="Enter resource type"
                            className="rounded-lg border border-gray-300 p-2"
                        />
                    </label>


                    <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                        Resource ID
                        <input
                            type="text"
                            value={filters.resource_id}
                            onChange={(event) =>
                                setFilters((prev) => ({
                                    ...prev,
                                    resource_id: event.target.value,
                                }))
                            }
                            placeholder="Enter resource ID"
                            className="rounded-lg border border-gray-300 p-2"
                        />
                    </label>



                    <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
                        Action succeeded?
                        <select
                            value={filters.success}
                            onChange={(event) =>
                                setFilters((prev) => ({
                                    ...prev,
                                    success: event.target.value as ("" | "true" | "false"),
                                }))
                            }
                            className="rounded-lg border border-gray-300 p-2">
                            <option key={""} value={""}>
                                Any
                            </option>
                            <option key={"true"} value={"true"}>
                                True
                            </option>
                            <option key={"false"} value={"false"}>
                                False
                            </option>

                        </select>
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
                    placeholder="Search by IP address, user email, or user agent..."
                    className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3
                    text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"/>
            </div>

            <section
                aria-label="Session results"
                aria-busy={loading}
                className="min-h-0 flex-1 overflow-y-auto rounded-xl">
                {loading ? (
                    <p className="py-8 text-center text-gray-500">
                        Loading sessions...
                    </p>
                ) : filteredLogs.length === 0 ? (
                    <p className="py-8 text-center text-gray-500">
                        {auditList.length === 0 ? 'No logs found.' : 'No logs match your search.'}
                    </p>
                ) : (
                    <div className="space-y-3 pb-4">

                        {filteredLogs.map((log) => {
                            const toggle = expandedLogs.has(log.id);

                            return (
                                <button
                                    key={log.id}
                                    type="button"
                                    onClick={() => {
                                        setExpandedLogs((prev) => {
                                            const next = new Set(prev);

                                            if (next.has(log.id)) {
                                                next.delete(log.id);
                                            } else {
                                                next.add(log.id);
                                            }

                                            return next;
                                        });
                                    }}
                                    className="block w-full rounded-xl border border-gray-200 bg-white p-4
                                        text-left shadow-sm transition hover:border-blue-300 hover:shadow-md
                                        focus:outline-none focus:ring-2 focus:ring-blue-500
                                        disabled:cursor-not-allowed"
                                >
                                    {/* Audit log header */}
                                    <div className="flex flex-wrap items-start justify-between gap-3">
                                        <div className="min-w-0">
                                            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                                                {log.action}
                                            </p>

                                            <h2 className="mt-1 text-lg font-semibold text-gray-900">
                                                {log.user_email || log.user_id}
                                            </h2>

                                            <p className="mt-1 text-sm text-gray-500">
                                                {log.timestamp
                                                    ? new Date(log.timestamp).toLocaleString()
                                                    : "Timestamp unavailable"}
                                            </p>
                                        </div>

                                        <span
                                            className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${log.success
                                                ? "bg-green-100 text-green-800"
                                                : "bg-red-100 text-red-800"
                                                }`}
                                        >
                                            {log.success ? "Success" : "Failure"}
                                        </span>
                                    </div>

                                    {/* Main audit attributes */}
                                    <div className="mt-3 space-y-2 text-sm text-gray-600">
                                        <p>
                                            <span className="font-medium text-gray-800">
                                                Audit ID:
                                            </span>{" "}
                                            {log.id}
                                        </p>

                                        <p>
                                            <span className="font-medium text-gray-800">
                                                User ID:
                                            </span>{" "}
                                            {log.user_id}
                                        </p>

                                        <p>
                                            <span className="font-medium text-gray-800">
                                                Resource type:
                                            </span>{" "}
                                            {log.resource_type || "Not specified"}
                                        </p>

                                        <p>
                                            <span className="font-medium text-gray-800">
                                                Resource ID:
                                            </span>{" "}
                                            {log.resource_id || "Not specified"}
                                        </p>

                                        <p>
                                            <span className="font-medium text-gray-800">
                                                IP address:
                                            </span>{" "}
                                            {log.ip_address || "Not recorded"}
                                        </p>

                                        <p>
                                            <span className="font-medium text-gray-800">
                                                Device ID:
                                            </span>{" "}
                                            {log.device_id || "Not specified"}
                                        </p>

                                        <p>
                                            <span className="font-medium text-gray-800">
                                                User agent:
                                            </span>{" "}
                                            <span className="break-words">
                                                {log.user_agent || "Not recorded"}
                                            </span>
                                        </p>
                                    </div>

                                    {/* Expand/collapse indicator */}
                                    <div className="mt-4 flex items-center justify-between border-t border-gray-100 pt-3">
                                        <span className="text-sm font-medium text-blue-600">
                                            {toggle ? "Hide details" : "View details"}
                                        </span>

                                        <span
                                            aria-hidden="true"
                                            className={`text-gray-500 transition-transform ${toggle ? "rotate-180" : ""
                                                }`}
                                        >
                                            ▼
                                        </span>
                                    </div>

                                    {/* Expandable details section */}
                                    {toggle && (
                                        <div className="mt-3 rounded-lg bg-gray-50 p-3">
                                            <h3 className="mb-2 text-sm font-semibold text-gray-800">
                                                Details
                                            </h3>

                                            {log.details != null ? (
                                                <pre className="overflow-x-auto whitespace-pre-wrap break-words text-sm text-gray-700">
                                                    {JSON.stringify(log.details, null, 2)}
                                                </pre>
                                            ) : (
                                                <p className="text-sm text-gray-500">
                                                    No details available.
                                                </p>
                                            )}
                                        </div>
                                    )}
                                </button>
                            );
                        })}

                    </div>
                )}
            </section>

        </main>
    );
}