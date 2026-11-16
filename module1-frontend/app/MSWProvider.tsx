"use client";

import { useEffect, useState } from "react";

let mswStartPromise: Promise<void> | null = null;

export default function MSWProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    async function startMSW() {
      // Mocks are opt-in: only when NEXT_PUBLIC_USE_MOCKS=true (dev only)
      if (
        process.env.NODE_ENV !== "development" ||
        process.env.NEXT_PUBLIC_USE_MOCKS !== "true"
      ) {
        setReady(true);
        return;
      }

      if (!mswStartPromise) {
        mswStartPromise = (async () => {
          const { worker } = await import("../mocks/browser");

          await worker.start({
            onUnhandledRequest: "bypass",
          });
        })();
      }

      await mswStartPromise;
      setReady(true);
    }

    startMSW();
  }, []);

  if (!ready) {
    return null;
  }

  return children;
}