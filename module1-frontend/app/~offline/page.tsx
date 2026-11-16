"use client";
export default function OfflinePage() {
    return (
        <main className="mx-auto flex min-h-screen max-w-lg flex-col items-center justify-center px-6 text-center">
            <h1 className="text-2xl font-bold">
                You are offline
            </h1>

            <p className="mt-4 text-gray-600">
                SAIV cannot reach the server right now. Check your
                internet connection and try again.
            </p>

            <button
                type="button"
                onClick={() => window.location.reload()}
                className="mt-6 rounded-lg bg-blue-600 px-5 py-2 text-white hover:bg-blue-700"
            >
                Try again
            </button>
        </main>
    );
}