"use client";

import { useEffect } from "react";
import { useAuth } from "@/app/components/AuthContext";
import { syncPendingCheckins } from "@/app/lib/checkinSync";

export default function CheckinSyncProvider() {
    const { user } = useAuth();
    const userId = user?.id;

    useEffect(() => {
        // Do not attempt synchronization without an authenticated user.
        if (!userId || user.role !== 'student') {
            return;
        }

        const sync = () => {
            void syncPendingCheckins();
        };

        const handleVisibilityChange = () => {
            if (document.visibilityState === "visible") {
                sync();
            }
        };

        // Retry when the user logs in or the provider mounts.
        sync();

        // Retry when connectivity returns.
        window.addEventListener("online", sync);

        // Retry when the user returns to the app.
        document.addEventListener(
            "visibilitychange",
            handleVisibilityChange
        );

        return () => {
            window.removeEventListener("online", sync);
            document.removeEventListener(
                "visibilitychange",
                handleVisibilityChange
            );
        };
    }, [userId]);

    return null;
}