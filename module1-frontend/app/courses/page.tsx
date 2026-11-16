"use client";

import { useAuth, apiFetch } from "../components/AuthContext";
import { useRouter } from "next/navigation";
import { useState, useMemo } from "react";
import { useFeedback } from '@/app/components/FeedbackContext';

type Filter = {
  semester: string,
  instructor_id: string,
  is_active: boolean,
  limit: number,
  page_number: number
}

type Course = {
  id: string,
  code: string,
  name: string,
  semester: string,
  instructor_name: string,
  venue_name: string,
  is_active: boolean
}


export default function CoursesPage() {

  const { isAuthenticated, user } = useAuth();
  const [filters, setFilters] = useState<Filter>({
    semester: "",
    instructor_id: "",
    is_active: true,
    limit: 50,
    page_number: 1
  });
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const router = useRouter();
  const [courseList, setCourseList] = useState<Course[]>([]);
  const [total, setTotal] = useState(0);
  const { setMsg } = useFeedback();

  async function fetchData(event: React.FormEvent<HTMLFormElement> | null) {

    if (event) {
      event.preventDefault();
    }

    setLoading(true);

    try {

      const params = new URLSearchParams();

      if (filters.semester !== "") {
        params.set('semester', filters.semester);
      }

      if (filters.instructor_id !== "") {
        params.set('instructor_id', filters.instructor_id);
      }

      params.set('is_active', String(filters.is_active));
      params.set('limit', String(filters.limit));
      params.set('offset', String((filters.page_number - 1) * filters.limit));

      const query = params.toString();

      const response = await apiFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/courses?${query}`, {
        method: 'GET'
      });

      const data = await response?.json();

      if (!response?.ok) {
        throw new Error("Error: " + (response?.status || "") + " " + (data.detail || "Request failed"));
      }


      setCourseList(data.items as Course[]);
      setTotal(data.total);


    } catch (error) {
      setMsg(error instanceof Error ? error.message : "Request failed", true);
    }

    setLoading(false);

  }

  const filteredCourses = useMemo<Course[]>(() => {

    const query = search.trim().toLowerCase();

    if (!query) return courseList;

    return courseList.filter((course) =>
      [
        course.name,
        course.semester,
        course.code,
        course.instructor_name,
        course.venue_name

      ].some((value) => value?.toLowerCase().includes(query))
    );

  }, [courseList, search]);

  if (!isAuthenticated()) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-gray-100">

        <div className="flex w-full mb-4 flex-row justify-evenly mt-auto">
          <h1 className="text-4xl font-bold w-full text-center text-white m-8">
            You need to be logged in to access this page
          </h1>
          <button className="text-lg w-1/4 text-center p-4 font-bold shadow-2xl rounded-lg bg-white hover:bg-gray-100"
            type="button" onClick={() => router.push('/login')}>
            Log in
          </button>
          <button className="text-lg w-1/4 text-center p-4 font-bold shadow-2xl rounded-lg bg-white hover:bg-gray-100"
            type="button" onClick={() => router.push('/register')}>
            Register
          </button>
        </div>

      </main>
    );
  }

  return (
    <main className="mx-auto flex h-[calc(100vh-4rem)] max-w-5xl flex-col gap-5 p-4 sm:p-6">
      <header>
        <h1 className="text-3xl font-bold text-gray-900">
          Courses
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Browse courses.
        </p>
      </header>

      <form
        onSubmit={fetchData}
        className="shrink-0 space-y-4 rounded-xl border border-gray-200 bg-white p-4">
        <h2 className="font-semibold text-gray-900">
          Filter courses.
        </h2>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">

          <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
            Semester
            <input
              type="text"
              value={filters.semester}
              onChange={(event) =>
                setFilters((prev) => ({
                  ...prev,
                  semester: event.target.value,
                }))
              }
              placeholder="Enter semester"
              className="rounded-lg border border-gray-300 p-2"
            />
          </label>

          <label className="flex flex-col gap-1 text-sm font-medium text-gray-700">
            Instructor ID
            <input
              type="text"
              value={filters.instructor_id}
              onChange={(event) =>
                setFilters((prev) => ({
                  ...prev,
                  instructor_id: event.target.value,
                }))
              }
              placeholder="Enter instructor ID"
              className="rounded-lg border border-gray-300 p-2"
            />
          </label>

          <label className="flex items-center gap-2 self-end pb-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={filters.is_active}
              onChange={(event) =>
                setFilters((prev) => ({
                  ...prev,
                  is_active: event.target.checked,
                }))
              }
              className="h-4 w-4 rounded"
            />
            Currently active
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

        {user?.role === "admin" && (
          <button
            type="button"
            onClick={() => router.push('/courses/new-course')}
            className="ml-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
            Create course
          </button>
        )}
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
          placeholder="Search by name, course code, instructor, venue, or semester..."
          className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3
                    text-sm text-gray-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"/>
      </div>

      {/* Scrollable session list */}
      <section
        aria-label="Session results"
        aria-busy={loading}
        className="min-h-0 flex-1 overflow-y-auto rounded-xl">
        {loading ? (
          <p className="py-8 text-center text-gray-500">
            Loading sessions...
          </p>
        ) : filteredCourses.length === 0 ? (
          <p className="py-8 text-center text-gray-500">
            {courseList.length === 0 ? 'No courses found.' : 'No courses match your search.'}
          </p>
        ) : (
          <div className="space-y-3 pb-4">
            {filteredCourses.map((course) => (
              <button
                key={course.id}
                type="button"
                disabled={!isAuthenticated()}
                onClick={() => router.push(`/courses/details?id=${encodeURIComponent(course.id)}`)}
                className="block w-full rounded-xl border border-gray-200 bg-white p-4 disabled:cursor-not-allowed
                                      text-left shadow-sm transition hover:border-blue-300 hover:shadow-md
                                      focus:outline-none focus:ring-2 focus:ring-blue-500">

                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                      {course.code}
                    </p>
                    <h2 className="mt-1 text-lg font-semibold text-gray-900">
                      {course.name}
                    </h2>
                  </div>

                  <span
                    className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${course.is_active
                      ? 'bg-green-100 text-green-800'
                      : 'bg-red-100 text-red-800'}`}>
                    {course.is_active ? "Active" : "Inactive"}
                  </span>
                </div>

                <div className="mt-3 space-y-2 text-sm text-gray-600">
                  <p>
                    <span className="font-medium text-gray-800">
                      Venue:
                    </span>{' '}
                    {course.venue_name || 'Not specified'}
                  </p>

                  <p>
                    <span className="font-medium text-gray-800">
                      Instructor:
                    </span>{' '}
                    {course.instructor_name || 'Not specified'}
                  </p>

                  <p>
                    <span className="font-medium text-gray-800">
                      Semester:
                    </span>{' '}
                    {course.semester || 'Not specified'}
                  </p>
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      <p className="shrink-0 text-xs text-gray-500">
        Showing {filteredCourses.length} of ${total} courses
      </p>

    </main>

  );
}