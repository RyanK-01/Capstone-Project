"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, useAuth } from "@/app/components/AuthContext";
import { useFeedback } from "@/app/components/FeedbackContext";

type CourseForm = {
  code: string;
  name: string;
  semester: string;
  instructor_id: string;
  venue_name: string;
  venue_latitude: string;
  venue_longitude: string;
  geofence_radius_meters: string;
  risk_threshold: string;
};

const initialForm: CourseForm = {
  code: "",
  name: "",
  semester: "",
  instructor_id: "",
  venue_name: "",
  venue_latitude: "",
  venue_longitude: "",
  geofence_radius_meters: "100",
  risk_threshold: "0.5",
};

export default function NewCoursePage() {
  const { user } = useAuth();
  const { setMsg } = useFeedback();
  const router = useRouter();

  const [form, setForm] = useState<CourseForm>(initialForm);
  const [submitting, setSubmitting] = useState(false);

  function updateField<K extends keyof CourseForm>(
    field: K,
    value: CourseForm[K]
  ) {
    setForm((prev) => ({
      ...prev,
      [field]: value,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const code = form.code.trim().toUpperCase();

    if (code.length !== 6) {
      setMsg("Course code must contain exactly 6 characters.", true);
      return;
    }

    const latitude = Number(form.venue_latitude);
    const longitude = Number(form.venue_longitude);
    const radius = Number(form.geofence_radius_meters);
    const riskThreshold = Number(form.risk_threshold);

    if (
      !Number.isFinite(latitude) ||
      latitude < -90 ||
      latitude > 90
    ) {
      setMsg("Latitude must be between -90 and 90.", true);
      return;
    }

    if (
      !Number.isFinite(longitude) ||
      longitude < -180 ||
      longitude > 180
    ) {
      setMsg("Longitude must be between -180 and 180.", true);
      return;
    }

    if (!Number.isFinite(radius) || radius <= 0) {
      setMsg("Geofence radius must be greater than zero.", true);
      return;
    }

    if (
      !Number.isFinite(riskThreshold) ||
      riskThreshold < 0 ||
      riskThreshold > 1
    ) {
      setMsg("Risk threshold must be between 0 and 1.", true);
      return;
    }

    const payload = {
      code,
      name: form.name.trim(),
      semester: form.semester.trim(),
      instructor_id: form.instructor_id.trim(),
      venue_name: form.venue_name.trim(),
      venue_latitude: latitude,
      venue_longitude: longitude,
      geofence_radius_meters: radius,
      risk_threshold: riskThreshold,
    };

    setSubmitting(true);

    try {
      const response = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/courses/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        let errorMessage = "Failed to create course.";

        try {
          const errorData = await response.json();
          errorMessage =
            typeof errorData.detail === "string"
              ? errorData.detail
              : typeof errorData.message === "string"
                ? errorData.message
                : errorMessage;
        } catch {

        }

        setMsg(errorMessage, true);
        return;
      }

      setMsg("Course created successfully.", false);
      setForm(initialForm);
    } catch {
      setMsg("A network error occurred while creating the course.", true);
    } finally {
      setSubmitting(false);
    }
  }

  if (user?.role !== "admin") {
    return (
      <main className="min-h-screen bg-gray-50 px-4 py-12">
        <div className="mx-auto max-w-xl rounded-2xl border border-red-200 bg-white p-8 text-center shadow-sm">
          <h1 className="text-2xl font-bold text-gray-900">
            Access denied
          </h1>
          <p className="mt-3 text-gray-600">
            Only administrators can create courses.
          </p>
          <button
            type="button"
            onClick={() => router.back()}
            className="mt-6 rounded-lg bg-gray-800 px-5 py-2.5 font-semibold text-white hover:bg-gray-700"
          >
            Go back
          </button>
        </div>
      </main>
    );
  }

  const inputClass =
    "mt-1.5 block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 shadow-sm outline-none transition placeholder:text-gray-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-gray-100";

  const labelClass = "block text-sm font-medium text-gray-700";

  return (
    <main className="min-h-screen bg-gray-50 px-4 py-8 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-4xl">
        {/* Page header */}
        <header className="mb-8">
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-gray-900">
            Create a new course
          </h1>
        </header>

        <form
          onSubmit={handleSubmit}
          className="space-y-8 rounded-2xl border border-gray-200 bg-white p-6 shadow-sm sm:p-8"
        >
          {/* Course information */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900">
              Course information
            </h2>

            <div className="mt-5 grid grid-cols-1 gap-2 sm:grid-cols-8">
              <div>
                <label htmlFor="code" className={labelClass}>
                  Course code <span className="text-red-600">*</span>
                </label>
                <input
    
                  id="code"
                  name="code"
                  type="text"
                  required
                  minLength={6}
                  maxLength={6}
                  pattern=".{6}"
                  title="Course code must contain exactly 6 characters."
                  autoComplete="off"
                  placeholder="e.g. CS6101"
                  value={form.code}
                  onChange={(event) =>
                    updateField("code", event.target.value.toUpperCase())
                  }
                  className={inputClass + "text-center"}
                />
                <p className="text-center mt-1 text-xs text-gray-500">
                  6 characters
                </p>
              </div>

              <div className="sm:col-span-7">
                <label htmlFor="name" className={labelClass}>
                  Course name <span className="text-red-600">*</span>
                </label>
                <input
                  id="name"
                  name="name"
                  type="text"
                  required
                  maxLength={200}
                  placeholder="e.g. Advanced Topics in CS"
                  value={form.name}
                  onChange={(event) =>
                    updateField("name", event.target.value)
                  }
                  className={inputClass}
                />
              </div>

              <div className="sm:col-span-8">
                <label htmlFor="semester" className={labelClass}>
                  Semester <span className="text-red-600">*</span>
                </label>
                <input
                  id="semester"
                  name="semester"
                  type="text"
                  required
                  placeholder="e.g. AY2026-27 Sem 1"
                  value={form.semester}
                  onChange={(event) =>
                    updateField("semester", event.target.value)
                  }
                  className={inputClass}
                />
              </div>

              <div className="sm:col-span-8">
                <label htmlFor="instructor_id" className={labelClass}>
                  Instructor UUID <span className="text-red-600">*</span>
                </label>
                <input
                  id="instructor_id"
                  name="instructor_id"
                  type="text"
                  required
                  placeholder="Enter the instructor's user UUID"
                  value={form.instructor_id}
                  onChange={(event) =>
                    updateField("instructor_id", event.target.value)
                  }
                  className={inputClass}
                />
                <p className="mt-1 text-xs text-gray-500">
                  Enter the instructor's existing user ID.
                </p>
              </div>
            </div>
          </section>

          <div className="border-t border-gray-200" />

          {/* Venue */}
          <section>
            <h2 className="text-lg font-semibold text-gray-900">
              Venue and geofence
            </h2>

            <div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label htmlFor="venue_name" className={labelClass}>
                  Venue name <span className="text-red-600">*</span>
                </label>
                <input
                  id="venue_name"
                  name="venue_name"
                  type="text"
                  required
                  placeholder="e.g. LT1"
                  value={form.venue_name}
                  onChange={(event) =>
                    updateField("venue_name", event.target.value)
                  }
                  className={inputClass}
                />
              </div>

              <div>
                <label htmlFor="venue_latitude" className={labelClass}>
                  Latitude <span className="text-red-600">*</span>
                </label>
                <input
                  id="venue_latitude"
                  name="venue_latitude"
                  type="number"
                  required
                  min="-90"
                  max="90"
                  step="any"
                  placeholder="e.g. 1.3483"
                  value={form.venue_latitude}
                  onChange={(event) =>
                    updateField("venue_latitude", event.target.value)
                  }
                  className={inputClass}
                />
                <p className="mt-1 text-xs text-gray-500">
                  Range: −90 to 90.
                </p>
              </div>

              <div>
                <label htmlFor="venue_longitude" className={labelClass}>
                  Longitude <span className="text-red-600">*</span>
                </label>
                <input
                  id="venue_longitude"
                  name="venue_longitude"
                  type="number"
                  required
                  min="-180"
                  max="180"
                  step="any"
                  placeholder="e.g. 103.6831"
                  value={form.venue_longitude}
                  onChange={(event) =>
                    updateField("venue_longitude", event.target.value)
                  }
                  className={inputClass}
                />
                <p className="mt-1 text-xs text-gray-500">
                  Range: −180 to 180.
                </p>
              </div>

              <div>
                <label
                  htmlFor="geofence_radius_meters"
                  className={labelClass}
                >
                  Geofence radius (metres){" "}
                  <span className="text-red-600">*</span>
                </label>
                <input
                  id="geofence_radius_meters"
                  name="geofence_radius_meters"
                  type="number"
                  required
                  min="0.01"
                  step="any"
                  value={form.geofence_radius_meters}
                  onChange={(event) =>
                    updateField(
                      "geofence_radius_meters",
                      event.target.value
                    )
                  }
                  className={inputClass}
                />
                <p className="mt-1 text-xs text-gray-500">
                  Students must be within the configured radius.
                </p>
              </div>

              <div>
                <label htmlFor="risk_threshold" className={labelClass}>
                  Risk threshold <span className="text-red-600">*</span>
                </label>
                <input
                  id="risk_threshold"
                  name="risk_threshold"
                  type="number"
                  required
                  min="0"
                  max="1"
                  step="0.01"
                  value={form.risk_threshold}
                  onChange={(event) =>
                    updateField("risk_threshold", event.target.value)
                  }
                  className={inputClass}
                />
                <p className="mt-1 text-xs text-gray-500">
                  A value between 0 and 1.
                </p>
              </div>
            </div>
          </section>

          {/* Form actions */}
          <div className="flex flex-col-reverse gap-3 border-t border-gray-200 pt-6 sm:flex-row sm:justify-end">
            <button
              type="button"
              disabled={submitting}
              onClick={() => router.back()}
              className="rounded-lg border border-gray-300 bg-white px-5 py-2.5 text-sm font-semibold text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-blue-300"
            >
              {submitting ? "Creating course..." : "Create course"}
            </button>
          </div>
        </form>
      </div>
    </main>
  );
}