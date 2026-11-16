
import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-[70vh] flex-col items-center justify-center px-6 text-center">
      <h1 className="text-5xl font-bold mb-4">
        Coming Soon
      </h1>

      <p className="text-gray-500 text-lg mb-8">
        We're working on this feature.
        Check back later!
      </p>

      <Link
        href="/"
        className="rounded-lg bg-blue-600 px-6 py-3
                   text-white font-medium
                   hover:bg-blue-700 transition-colors"
      >
        Back to Home
      </Link>
    </main>
  );
}
