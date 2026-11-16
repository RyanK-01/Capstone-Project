"use client";

import { useEffect } from "react";

export default function RegisterServiceWorker() {
    useEffect(() => {
        if (
            process.env.NODE_ENV === "production" &&
            "serviceWorker" in navigator &&
            window.serwist
        ) {
            void window.serwist.register();
        }
    }, []);

    return null;
}
