"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { apiFetch, useAuth } from "@/app/components/AuthContext";
import { useFeedback } from "@/app/components/FeedbackContext";
import { type Checkin, type RiskFactor } from "@/app/lib/types";
import { useEffect, useState } from "react";
import { formatDate } from "@/app/lib/utils";


export default function CheckinDetailsPage() {

    const searchParams = useSearchParams();
    const { setMsg } = useFeedback();
    const [checkin, setCheckin] = useState<Checkin | null>(null);
    const { isAuthenticated, user } = useAuth();
    const router = useRouter();
    const [appeal, setAppeal] = useState<string | null>(null);
    const [review, setReview] = useState<string | null>(null);


    const id = searchParams.get('id');

    async function fetchData() {

        try {

            if (!id) {
                throw new Error("Invalid checkin ID");
            }
            
            const response = await apiFetch(
                `${process.env.NEXT_PUBLIC_API_BASE_URL}/checkins/${id}`,
                { method: 'GET' }
            );

            if (!response.ok) {
                const data = await response.json();
                let altMessage = "Request failed";

                switch (response.status) {
                    case 401: {
                        altMessage = "Invalid credentials or you don't have access to this checkin log";
                        break;
                    }
                    case 403: {
                        altMessage = "Account disabled";
                        break;
                    }
                    case 404: {
                        altMessage = "Checkin could not be found";
                        break;
                    }
                    default: {
                        altMessage = "Request failed (" + response.status + ")";
                    }
                }
                throw new Error(data.detail || altMessage);
            }

            const data = await response.json() as Checkin;
            setMsg("", true);
            setCheckin(data as Checkin);
            setAppeal(data.appeal_reason);
            setReview(data.review_notes);

        }
        catch (error) {

            setMsg(error instanceof Error ? error.message : "Checkin details failed to load or you don't have access to this checkin log", true);
            setCheckin(null);

        }

    }

    async function submitAppeal() {
        try {

            if (!id) {
                throw new Error("Invalid checkin ID");
            }

            const response = await apiFetch(
                `${process.env.NEXT_PUBLIC_API_BASE_URL}/checkins/${id}/appeal`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    appeal_reason: appeal,
                })
            });

            if (!response.ok) {
                const data = await response.json();
                let altMessage = "Request failed";

                switch (response.status) {
                    case 401: {
                        altMessage = "Invalid credentials or you don't have access to this checkin log";
                        break;
                    }
                    case 403: {
                        altMessage = "Account disabled";
                        break;
                    }
                    case 404: {
                        altMessage = "Checkin could not be found";
                        break;
                    }
                    default: {
                        altMessage = "Request failed (" + response.status + ")";
                    }
                }
                throw new Error(data.detail || altMessage);
            }

            const data = await response.json();
            setMsg("Appeal submitted with ID: " + data.id, false);
            setCheckin((prev) => prev ? { ...prev, status: data.status, appeal_reason: data.appeal_reason, appealed_at: data.appealed_at } : prev);
            setAppeal(data.appeal_reason);

        }
        catch (error) {

            setMsg(error instanceof Error ? error.message : "Checkin details failed to load or you don't have access to this checkin log", true);

        }

    }

    async function submitReview(verdict: boolean) {
        try {

            if (!id) {
                throw new Error("Invalid checkin ID");
            }

            const response = await apiFetch(
                `${process.env.NEXT_PUBLIC_API_BASE_URL}/checkins/${id}/review`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    status: `${verdict ? "approved" : "rejected"}`,
                    review_notes: review,
                })
            });

            if (!response.ok) {
                const data = await response.json();
                let altMessage = "Request failed";

                switch (response.status) {
                    case 401: {
                        altMessage = "Invalid credentials or you don't have access to this checkin log";
                        break;
                    }
                    case 403: {
                        altMessage = "Account disabled";
                        break;
                    }
                    case 404: {
                        altMessage = "Checkin could not be found";
                        break;
                    }
                    default: {
                        altMessage = "Request failed (" + response.status + ")";
                    }
                }
                throw new Error(data.detail || altMessage);
            }

            const data = await response.json();
            setMsg("Review submitted with ID: " + data.id, false);
            setCheckin((prev) => prev ? { ...prev, status: data.status, review_notes: data.review_notes, reviewed_at: data.reviewed_at, reviewed_by_id: data.reviewed_by_id } : prev);
            setReview(data.review_notes);

        }
        catch (error) {

            setMsg(error instanceof Error ? error.message : "Checkin details failed to load or you don't have access to this checkin log", true);

        }

    }

    useEffect(() => {
        fetchData();
    }, [])

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


        <main className="mx-auto w-full max-w-6xl space-y-6 text-gray-900">

            {/* Header */}
            <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0">
                        <p className="text-sm font-medium uppercase tracking-wide text-gray-500">
                            Check-in details
                        </p>
                        <h1 className="mt-2 break-all text-xl font-bold sm:text-2xl">
                            {checkin?.id}
                        </h1>
                        <p className="mt-2 text-sm text-gray-500">
                            Submitted {formatDate(checkin?.checked_in_at || "")}
                        </p>
                    </div>

                    <span
                        className={`inline-flex w-fit items-center rounded-full px-3 py-1.5 text-sm font-semibold ${{
                            pending: "bg-yellow-100 text-yellow-800",
                            approved: "bg-green-100 text-green-800",
                            flagged: "bg-orange-100 text-orange-800",
                            rejected: "bg-red-100 text-red-800",
                            appealed: "bg-purple-100 text-purple-800",
                            "All statuses": "bg-gray-100 text-gray-700"
                        }[checkin?.status || "pending"] ?? "bg-gray-100 text-gray-700"
                            }`}
                    >
                        {(checkin?.status || "").charAt(0).toUpperCase() +
                            checkin?.status.slice(1)}
                    </span>
                </div>
            </section>

            {/* General information */}
            <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <h2 className="mb-5 text-lg font-bold">General information</h2>

                <dl className="grid grid-cols-1 gap-x-8 gap-y-5 sm:grid-cols-2 lg:grid-cols-3">
                    {[
                        ["Session ID", checkin?.session_id],
                        ["Student ID", checkin?.student_id],
                        ["Device ID", checkin?.device_id],
                        ["Checked in at", formatDate(checkin?.checked_in_at || "")],
                        ["Verified at", checkin?.verified_at ? formatDate(checkin?.verified_at || "") : null],
                        ["GPS accuracy", checkin?.location_accuracy_meters != null
                            ? `${checkin?.location_accuracy_meters} m`
                            : null],
                        ["Distance from venue", checkin?.distance_from_venue_meters != null
                            ? `${checkin?.distance_from_venue_meters} m`
                            : null],
                        ["QR code verified", checkin?.qr_code_verified],
                    ].map(([label, value]) => (
                        <div key={String(label)} className="min-w-0">
                            <dt className="text-sm text-gray-500">{label}</dt>
                            <dd className="mt-1 break-words font-medium">
                                {value == null || value === ""
                                    ? "—"
                                    : typeof value === "boolean"
                                        ? value ? "Yes" : "No"
                                        : value}
                            </dd>
                        </div>
                    ))}
                </dl>
            </section>

            {/* Verification results */}
            <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <h2 className="mb-5 text-lg font-bold">Verification results</h2>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">

                    {/* Liveness */}
                    <div className="rounded-xl border border-gray-200 p-4">
                        <p className="text-sm text-gray-500">Liveness check</p>
                        <p className={`mt-2 text-lg font-semibold ${checkin?.liveness_passed == null
                            ? "text-gray-500"
                            : checkin?.liveness_passed
                                ? "text-green-700"
                                : "text-red-700"
                            }`}>
                            {checkin?.liveness_passed == null
                                ? "Not available"
                                : checkin?.liveness_passed
                                    ? "Passed"
                                    : "Failed"}
                        </p>

                        <p className="mt-2 text-sm text-gray-600">
                            Score: {checkin?.liveness_score != null
                                ? `${(checkin?.liveness_score * 100).toFixed(1)}%`
                                : "—"}
                        </p>

                        <p className="mt-1 text-sm text-gray-600">
                            Challenge: {checkin?.liveness_challenge_type ?? "—"}
                        </p>
                    </div>

                    {/* Face match */}
                    <div className="rounded-xl border border-gray-200 p-4">
                        <p className="text-sm text-gray-500">Facial verification</p>
                        <p className={`mt-2 text-lg font-semibold ${checkin?.face_match_passed == null
                            ? "text-gray-500"
                            : checkin?.face_match_passed
                                ? "text-green-700"
                                : "text-red-700"
                            }`}>
                            {checkin?.face_match_passed == null
                                ? "Not available"
                                : checkin?.face_match_passed
                                    ? "Matched"
                                    : "Not matched"}
                        </p>

                        <p className="mt-2 text-sm text-gray-600">
                            Similarity score: {checkin?.face_match_score != null
                                ? `${(checkin?.face_match_score * 100).toFixed(1)}%`
                                : "—"}
                        </p>
                    </div>

                    {/* Risk score */}
                    <div className="rounded-xl border border-gray-200 p-4">
                        <p className="text-sm text-gray-500">Risk score</p>

                        <p className={`mt-2 text-2xl font-bold ${!(checkin?.risk_score) ? "text-gray-800" : checkin?.risk_score >= 0.75
                            ? "text-red-700"
                            : checkin?.risk_score >= 0.5
                                ? "text-orange-700"
                                : checkin?.risk_score >= 0.25
                                    ? "text-yellow-700"
                                    : "text-green-700"
                            }`}>
                            {(checkin?.risk_score) ? (checkin?.risk_score * 100).toFixed(1) : "undefined"}%
                        </p>

                        <div
                            className="mt-3 h-2 w-full overflow-hidden rounded-full bg-gray-100"
                            role="progressbar"
                            aria-label="Risk score"
                            aria-valuemin={0}
                            aria-valuemax={100}
                            aria-valuenow={(checkin?.risk_score) ? Math.round(checkin?.risk_score * 100) : 0}
                        >
                            <div
                                className={`h-full rounded-full ${!(checkin?.risk_score) ? "bg-gray-300" : checkin?.risk_score >= 0.75
                                    ? "bg-red-500"
                                    : checkin?.risk_score >= 0.5
                                        ? "bg-orange-500"
                                        : checkin?.risk_score >= 0.25
                                            ? "bg-yellow-500"
                                            : "bg-green-500"
                                    }`}
                                style={{
                                    width: `${(checkin?.risk_score) ? Math.max(0, Math.min(1, checkin?.risk_score)) * 100 : 0}%`,
                                }}
                            />
                        </div>
                    </div>

                </div>
            </section>


            {/* Risk factors */}
            {user?.role !== "student" && (
                <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                    <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                        <div>
                            <h2 className="text-lg font-bold">Risk factors</h2>
                            <p className="mt-1 text-sm text-gray-500">
                                Signals contributing to the check-in risk assessment.
                            </p>
                        </div>

                        <span className="rounded-full bg-gray-100 px-3 py-1 text-sm font-semibold text-gray-700">
                            {(() => {
                                try {
                                    const factors = typeof checkin?.risk_factors === "string"
                                        ? JSON.parse(checkin?.risk_factors || "[]")
                                        : checkin?.risk_factors;

                                    return Array.isArray(factors) ? factors.length : 0;
                                } catch {
                                    return "Invalid data";
                                }
                            })()}{" "}
                            {(() => {
                                try {
                                    const factors = typeof checkin?.risk_factors === "string"
                                        ? JSON.parse(checkin?.risk_factors || "[]")
                                        : checkin?.risk_factors;

                                    return Array.isArray(factors) && factors.length === 1
                                        ? "factor"
                                        : "factors";
                                } catch {
                                    return "";
                                }
                            })()}
                        </span>
                    </div>

                    {(() => {
                        let factors: RiskFactor[] = [];

                        try {
                            const parsed = typeof checkin?.risk_factors === "string"
                                ? JSON.parse(checkin?.risk_factors || "[]")
                                : checkin?.risk_factors;

                            if (Array.isArray(parsed)) {
                                factors = parsed;
                            }
                        } catch {
                            return (
                                <p className="rounded-lg bg-red-50 p-4 text-sm text-red-700">
                                    Risk-factor data could not be parsed.
                                </p>
                            );
                        }

                        if (factors.length === 0) {
                            return (
                                <p className="rounded-lg bg-gray-50 p-4 text-sm text-gray-600">
                                    No risk factors recorded for this check-in.
                                </p>
                            );
                        }

                        const severityStyles: Record<string, string> = {
                            low: "bg-blue-100 text-blue-800",
                            medium: "bg-yellow-100 text-yellow-800",
                            high: "bg-orange-100 text-orange-800",
                            critical: "bg-red-100 text-red-800",
                        };

                        const signalLabels: Record<string, string> = {
                            geo_out_of_bounds: "Outside geofence",
                            impossible_travel: "Impossible travel",
                            geo_accuracy_low: "Low GPS accuracy",
                            vpn_detected: "VPN detected",
                            proxy_detected: "Proxy detected",
                            tor_detected: "Tor detected",
                            suspicious_ip: "Suspicious IP address",
                            device_unknown: "Unknown device",
                            device_emulator: "Emulator detected",
                            device_rooted: "Rooted device",
                            attestation_failed: "Device attestation failed",
                            rapid_succession: "Rapid check-in attempts",
                            unusual_time: "Unusual check-in time",
                            pattern_anomaly: "Behavioural anomaly",
                            liveness_failed: "Liveness check failed",
                            liveness_low_confidence: "Low liveness confidence",
                            deepfake_suspected: "Suspected deepfake",
                            replay_suspected: "Suspected replay attack",
                            face_match_failed: "Face match failed",
                            face_match_low_confidence: "Low face-match confidence",
                        };

                        return (
                            <div className="space-y-4">
                                {factors.map((factor, index) => (
                                    <article
                                        key={`${factor.signal_type}-${index}`}
                                        className="rounded-xl border border-gray-200 p-4 sm:p-5"
                                    >
                                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                            <div className="min-w-0">
                                                <h3 className="font-semibold text-gray-900">
                                                    {signalLabels[factor.signal_type] ??
                                                        factor.signal_type.replaceAll("_", " ")}
                                                </h3>

                                                <p className="mt-1 break-words text-xs text-gray-500">
                                                    Signal: {factor.signal_type}
                                                </p>
                                            </div>

                                            <span className={`w-fit shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${severityStyles[factor.severity] ??
                                                "bg-gray-100 text-gray-700"
                                                }`}>
                                                {factor.severity.toUpperCase()}
                                            </span>
                                        </div>

                                        <dl className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                                            <div>
                                                <dt className="text-sm text-gray-500">Confidence</dt>
                                                <dd className="mt-1 font-medium text-gray-900">
                                                    {(factor.confidence * 100).toFixed(1)}%
                                                </dd>
                                            </div>

                                            <div>
                                                <dt className="text-sm text-gray-500">Risk contribution weight</dt>
                                                <dd className="mt-1 font-medium text-gray-900">
                                                    {factor.weight.toFixed(3)}
                                                </dd>
                                            </div>

                                            <div>
                                                <dt className="text-sm text-gray-500">Details</dt>
                                                <dd className="mt-1 break-words text-sm text-gray-700">
                                                    {(() => {
                                                        if (factor.details == null || factor.details === "") {
                                                            return "—";
                                                        }

                                                        if (typeof factor.details !== "string") {
                                                            return JSON.stringify(factor.details, null, 2);
                                                        }

                                                        try {
                                                            return JSON.stringify(
                                                                JSON.parse(factor.details),
                                                                null,
                                                                2
                                                            );
                                                        } catch {
                                                            return factor.details;
                                                        }
                                                    })()}
                                                </dd>
                                            </div>
                                        </dl>
                                    </article>
                                ))}
                            </div>
                        );
                    })()}
                </section>
            )}

            {/* Review and appeal */}
            <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <h2 className="mb-5 text-lg font-bold">Appeal</h2>

                <dl className="grid grid-cols-1 gap-5">

                    <div>
                        <dt className="text-sm text-gray-500">Appealed at</dt>
                        <dd className="mt-1 font-medium text-gray-900">
                            {checkin?.appealed_at ? formatDate(checkin?.appealed_at) : "—"}
                        </dd>
                    </div>

                    <div>
                        <dt className="text-sm text-gray-500">Appeal reason</dt>

                        <dd className="mt-1 w-full whitespace-pre-wrap text-gray-700">
                            <textarea className="w-full rounded-lg border border-transparent bg-transparent px-2 py-1 text-sm font-medium text-gray-900 transition
                                enabled:border-gray-300 enabled:bg-gray-50
                                enabled:hover:border-gray-400
                                focus:outline-none focus:ring-2 focus:ring-blue-500
                                disabled:cursor-default disabled:opacity-100"
                                disabled={user?.role !== "student" || checkin?.appeal_reason !== null || !(checkin?.status === "flagged" || checkin?.status == "rejected")}
                                value={appeal || ""}
                                placeholder="No appeal submitted."
                                onChange={(event) => setAppeal(event.target.value)}>
                            </textarea>
                        </dd>

                    </div>
                </dl>

                {user?.role === "student" && checkin?.appeal_reason === null && (checkin?.status === "flagged" || checkin?.status == "rejected") && (
                    <button
                        className="mt-4 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                        type="button"
                        onClick={() => {
                            submitAppeal();
                            setMsg("", true);
                        }}>
                        Submit appeal
                    </button>
                )}
            </section>


            {/* Review and appeal */}
            <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
                <h2 className="mb-5 text-lg font-bold">Review</h2>

                <dl className="grid grid-cols-1 gap-5 sm:grid-cols-2">

                    <div>
                        <dt className="text-sm text-gray-500">Reviewed by</dt>
                        <dd className="mt-1 break-all font-medium text-gray-900">
                            {checkin?.reviewed_by_id ?? "—"}
                        </dd>
                    </div>

                    <div>
                        <dt className="text-sm text-gray-500">Reviewed at</dt>
                        <dd className="mt-1 font-medium text-gray-900">
                            {checkin?.reviewed_at ? formatDate(checkin?.reviewed_at) : "—"}
                        </dd>
                    </div>

                    <div>
                        <dt className="text-sm text-gray-500">Review notes</dt>

                        <dd className="mt-1 w-full whitespace-pre-wrap text-gray-700">
                            <textarea className="w-full rounded-lg border border-transparent bg-transparent px-2 py-1 text-sm font-medium text-gray-900 transition
                                enabled:border-gray-300 enabled:bg-gray-50
                                enabled:hover:border-gray-400
                                focus:outline-none focus:ring-2 focus:ring-blue-500
                                disabled:cursor-default disabled:opacity-100"
                                disabled={user?.role === "student" || checkin?.review_notes !== null || !(checkin?.status === "flagged" || checkin?.status == "rejected")}
                                value={review || ""}
                                placeholder="No review submitted."
                                onChange={(event) => setReview(event.target.value)}>
                            </textarea>
                        </dd>

                    </div>

                </dl>

                {user?.role !== "student" && (checkin?.status === "flagged" || checkin?.status == "appealed") && (
                    <>
                        <button
                            className="mt-4 mr-8 rounded-lg bg-green-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                            type="button"
                            onClick={() => {
                                submitReview(true);
                                setMsg("", true);
                            }}>
                            Approve
                        </button>
                        <button
                            className="mt-4 rounded-lg bg-red-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                            type="button"
                            onClick={() => {
                                submitReview(false);
                                setMsg("", true);
                            }}>
                            Reject
                        </button>
                    </>
                )}
            </section>

        </main>

    );
}