"use client";

import { useSearchParams, useRouter } from 'next/navigation'
import { apiFetch, useAuth } from '@/app/components/AuthContext';
import { useFeedback } from '@/app/components/FeedbackContext'
import { useState, useEffect } from 'react';
import { formatDate, formatLocalToUTC, formatUTCToLocal } from '@/app/lib/utils';
import { type SessionStatus } from '@/app/lib/types';
import LocationMapLoader from '@/app/components/LocationMapLoader';

type SessionDetails = {
  id: string,
  course_id: string,
  instructor_id: string,
  name: string,
  session_type: string,
  status: SessionStatus,
  scheduled_start: string,
  scheduled_end: string,
  checkin_opens_at: string,
  checkin_closes_at: string,
  venue_latitude: number,
  venue_longitude: number,
  venue_name: string,
  geofence_radius_meters: number
  require_liveness_check: boolean,
  require_face_match: boolean,
  risk_threshold: number,
  qr_code_enabled: boolean,
  created_at: string
}

type EditDetails = {
  status: string,
  name: string,
  checkin_closes_at: string
}

export default function SessionsDetailsPage() {

  const [sessionDetails, setSessionDetails] = useState<SessionDetails | null>(null);
  const [editDetails, setEditDetails] = useState<EditDetails | null>(null);
  const { setMsg } = useFeedback();
  const { isAuthenticated, user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isEditing, setEditing] = useState(false);
  const [deleteSession, setDelete] = useState(false);

  const id = searchParams.get('id');

  async function fetchData() {

    try {

      if (!id) {
        throw new Error("Invalid session ID");
      }

      const response = await apiFetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/sessions/${id}`,
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
            altMessage = "Session could not be found";
            break;
          }
          default: {
            altMessage = "Request failed (" + response.status + ")";
          }
        }
        throw new Error(data.detail || altMessage);
      }

      const responseSession = await response.json() as SessionDetails;
    
      setSessionDetails(responseSession);
      setEditDetails(responseSession);

    }
    catch (error) {

      setMsg(error instanceof Error ? error.message : "Session details failed to load", true);
      setSessionDetails(null);
      setEditDetails(null);

    }

  }

  useEffect(() => {
    fetchData();
  }, [])

  async function submit() {
    try {

      let saveChanges = null;

      if (deleteSession) {
        saveChanges = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/sessions/` + sessionDetails?.id, {
          method: 'DELETE',
        });
      }
      else {
        saveChanges = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/sessions/` + sessionDetails?.id, {
          method: 'PATCH',
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

      if (deleteSession) {
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
<main className="min-h-screen w-full bg-gray-50 px-4 py-8 sm:px-6 lg:px-8">
  <div className="mx-auto max-w-6xl space-y-8">

    {/* Session header */}
    <header className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm sm:p-8">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 flex-1">
          <p className="mb-2 text-sm font-medium uppercase tracking-wider text-gray-500">
            Session details
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
              sm:text-3xl"
          />

          <p className="mt-2 break-all text-sm text-gray-500">
            Session ID: {sessionDetails?.id ?? "—"}
          </p>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-3">
          

            <select
              value={editDetails ? editDetails.status : ""}
              disabled={!isEditing}
              onChange={(event) => setEditDetails((prev) => prev ? { ...prev, status: event.target.value as SessionStatus } : null)}
              className={`text-center capitalize enabled:border disabled:border-0 border-blue-500 border-dashed border-2 appearance-none inline-flex items-center rounded-full px-3 py-1.5 text-sm font-semibold ${
              editDetails?.status === "active"
                ? "bg-green-100 text-green-800"
                : editDetails?.status === "scheduled"
                  ? "bg-blue-100 text-blue-800"
                  : editDetails?.status === "closed"
                    ? "bg-gray-200 text-gray-700"
                    : "bg-red-100 text-red-800"
            }`}>
              <option key={sessionDetails?.status} value={sessionDetails?.status}>
                {sessionDetails?.status}
              </option>
              {sessionDetails?.status === "scheduled" && (
                <option key={"active"} value={"active"}>
                  Active
                </option>
              )}
              {sessionDetails?.status === "active" && (
                <option key={"closed"} value={"closed"}>
                  Closed
                </option>
              )}
              <option key={"cancelled"} value={"cancelled"}>
                Cancelled
              </option>
            </select>
        </div>
      </div>
    </header>

    {/* Session information */}
    <section className="space-y-4">
      <h2 className="text-xl font-bold text-gray-900">
        General information
      </h2>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">

        {/* Basic details */}
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <h3 className="mb-5 text-base font-semibold text-gray-900">
            Overview
          </h3>

          <dl className="grid grid-cols-1 gap-5 sm:grid-cols-2">

            <div className="min-w-0">
              <dt className="text-sm text-gray-500">Course ID</dt>
              <dd className="mt-1 break-words font-medium text-gray-900">
                {sessionDetails?.course_id ?? "—"}
              </dd>
            </div>

            <div className="min-w-0">
              <dt className="text-sm text-gray-500">Instructor ID</dt>
              <dd className="mt-1 break-words font-medium text-gray-900">
                {sessionDetails?.instructor_id ?? "—"}
              </dd>
            </div>

            <div>
              <dt className="text-sm text-gray-500">Session type</dt>
              <dd className="mt-1 font-medium text-gray-900">
                {sessionDetails?.session_type ?? "—"}
              </dd>
            </div>

            <div>
              <dt className="text-sm text-gray-500">Created at</dt>
              <dd className="mt-1 font-medium text-gray-900">
                {sessionDetails
                  ? formatDate(sessionDetails.created_at)
                  : "—"}
              </dd>
            </div>

          </dl>
        </div>

        {/* Schedule */}
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <h3 className="mb-5 text-base font-semibold text-gray-900">
            Schedule
          </h3>

          <dl className="space-y-5">

            <div>
              <dt className="text-sm text-gray-500">Scheduled period</dt>
              <dd className="mt-1 font-medium text-gray-900">
                {sessionDetails
                  ? formatDate(sessionDetails.scheduled_start)
                  : "—"}
                <span className="mx-2 text-gray-400">to</span>
                {sessionDetails
                  ? formatDate(sessionDetails.scheduled_end)
                  : "—"}
              </dd>
            </div>

            <div>
              <dt className="mb-2 text-sm text-gray-500">
                Check-in window
              </dt>

              <dd className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label
                    htmlFor="checkin-opens"
                    className="mb-1 block text-xs font-medium text-gray-500"
                  >
                    Opens
                  </label>
                  <input
                    id="checkin-opens"
                    type="datetime-local"
                    disabled
                    value={
                      sessionDetails
                        ? formatUTCToLocal(sessionDetails.checkin_opens_at)
                        : ""
                    }
                    className="w-full min-w-0 rounded-lg border border-gray-200 bg-gray-100 px-3 py-2 text-sm text-gray-600 disabled:cursor-default disabled:opacity-100"
                  />
                </div>

                <div>
                  <label
                    htmlFor="checkin-closes"
                    className="mb-1 block text-xs font-medium text-gray-500"
                  >
                    Closes
                  </label>
                  <input
                    id="checkin-closes"
                    type="datetime-local"
                    disabled={!isEditing}
                    value={
                      editDetails
                        ? formatUTCToLocal(editDetails.checkin_closes_at)
                        : ""
                    }
                    onChange={(event) =>
                      setEditDetails((prev) =>
                        prev
                          ? {
                              ...prev,
                              checkin_closes_at: formatLocalToUTC(
                                event.target.value
                              ),
                            }
                          : null
                      )
                    }
                    className="w-full min-w-0 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 transition
                      focus:outline-none focus:ring-2 focus:ring-blue-500
                      disabled:cursor-default disabled:border-gray-200
                      disabled:bg-gray-100 disabled:opacity-100"
                  />
                </div>
              </dd>
            </div>

          </dl>
        </div>

      </div>
    </section>

    {/* Location */}
    <section className="space-y-4">
      <h2 className="text-xl font-bold text-gray-900">
        Session location
      </h2>

      <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">
        <div className="grid grid-cols-1 gap-6 p-6 sm:grid-cols-2 lg:grid-cols-3">

          <div className="min-w-0">
            <p className="text-sm text-gray-500">Venue</p>
            <p className="mt-1 break-words font-semibold text-gray-900">
              {sessionDetails?.venue_name ?? "—"}
            </p>
          </div>

          <div>
            <p className="text-sm text-gray-500">Geofence radius</p>
            <p className="mt-1 font-semibold text-gray-900">
              {sessionDetails?.geofence_radius_meters != null
                ? `${sessionDetails.geofence_radius_meters} m`
                : "—"}
            </p>
          </div>

          <div>
            <p className="text-sm text-gray-500">Coordinates</p>
            <p className="mt-1 break-words font-medium text-gray-900">
              {sessionDetails
                ? `${sessionDetails.venue_latitude}, ${sessionDetails.venue_longitude}`
                : "—"}
            </p>
          </div>

        </div>

        {sessionDetails && (
          <div className="border-t border-gray-200">
            <LocationMapLoader
              latitude={sessionDetails.venue_latitude}
              longitude={sessionDetails.venue_longitude}
              radiusMeters={sessionDetails.geofence_radius_meters}
            />
          </div>
        )}
      </div>
    </section>

    {/* Verification requirements */}
    <section className="space-y-4">
      <h2 className="text-xl font-bold text-gray-900">
        Check-in requirements
      </h2>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">

        {[
          {
            label: "Liveness check",
            enabled: sessionDetails?.require_liveness_check,
          },
          {
            label: "Facial verification",
            enabled: sessionDetails?.require_face_match,
          },
          {
            label: "QR code",
            enabled: sessionDetails?.qr_code_enabled,
          },
        ].map(({ label, enabled }) => (
          <div
            key={label}
            className="flex items-center justify-between gap-3 rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
          >
            <span className="text-sm font-medium text-gray-700">
              {label}
            </span>

            <span
              className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${
                enabled
                  ? "bg-blue-100 text-blue-800"
                  : "bg-gray-100 text-gray-600"
              }`}
            >
              {enabled == null ? "—" : enabled ? "Required" : "Not required"}
            </span>
          </div>
        ))}

        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
          <p className="text-sm font-medium text-gray-700">
            Risk threshold
          </p>
          <p className="mt-2 text-lg font-semibold text-gray-900">
            {sessionDetails?.risk_threshold ?? "—"}
          </p>
        </div>

      </div>
    </section>

    {/* Actions */}
    <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="mb-5 text-xl font-bold text-gray-900">
        Actions
      </h2>

      <div className="flex flex-wrap items-center gap-3">

        {!isEditing &&
          (user?.role === "admin" ||
            (user?.role === "instructor" &&
              user?.id === sessionDetails?.instructor_id)) && (
            <button
              className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
              type="button"
              onClick={() => {
                setEditing(true);
                setMsg("", true);
              }}
            >
              Edit session
            </button>
          )}

        {isEditing && (
          <>
            <button
              className="rounded-lg border border-gray-300 bg-white px-5 py-2.5 text-sm font-semibold text-gray-700 transition hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-2"
              type="button"
              onClick={() => {
                setEditing(false);
                setEditDetails(sessionDetails);
              }}
            >
              Cancel
            </button>

            <button
              className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-gray-300"
              type="button"
              onClick={() => {
                submit();
              }}
            >
              Save changes
            </button>

            <button
              className={`rounded-lg px-5 py-2.5 text-sm font-semibold shadow-sm transition focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40 ${
                deleteSession
                  ? "bg-red-700 text-white hover:bg-red-800 focus:ring-red-500"
                  : "border border-red-200 bg-white text-red-700 hover:bg-red-50 focus:ring-red-500"
              }`}
              type="button"
              disabled={sessionDetails?.status !== "scheduled"}
              onClick={() => setDelete(!deleteSession)}
            >
              {sessionDetails?.status !== "scheduled" ? "You can only delete \'Scheduled\' sessions" : deleteSession ? "Cancel deletion" : "Delete session"}
            </button>
          </>
        )}

        {!isEditing && user?.role !== "student" && (
          <>
            {(user?.role === "admin" ||
              (user?.role === "instructor" &&
                user?.id === sessionDetails?.instructor_id)) && (
              <button
                className="rounded-lg border border-gray-300 bg-white px-5 py-2.5 text-sm font-semibold text-gray-700 transition hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-2"
                type="button"
                onClick={() => {
                  router.push("/export/session?id=" + sessionDetails?.id);
                  setMsg("", true);
                }}
              >
                Export check-in data
              </button>
            )}

            <button
              className="rounded-lg border border-gray-300 bg-white px-5 py-2.5 text-sm font-semibold text-gray-700 transition hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-2"
              type="button"
              onClick={() => {
                router.push(
                  "/checkins?session-id=" +
                    sessionDetails?.id +
                    "&session-name=" +
                    encodeURIComponent(sessionDetails?.name || "")
                );
                setMsg("", true);
              }}
            >
              Check-in history
            </button>

            <button
              className="rounded-lg border border-gray-300 bg-white px-5 py-2.5 text-sm font-semibold text-gray-700 transition hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400"
              type="button"
              disabled={sessionDetails?.status !== "active"}
              onClick={() => {
                router.push(
                  "/stats/session?session-id=" + sessionDetails?.id
                );
                setMsg("", true);
              }}
            >
              View statistics
            </button>
          </>
        )}

        {user?.role === "student" && (
          <button
            className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-gray-300"
            type="button"
            disabled={sessionDetails?.status !== "active"}
            onClick={() => {
              router.push(
                "/sessions/checkin?session-id=" + sessionDetails?.id
              );
              setMsg("", true);
            }}
          >
            Check in
          </button>
        )}

      </div>
    </section>

  </div>
</main>

  );
}