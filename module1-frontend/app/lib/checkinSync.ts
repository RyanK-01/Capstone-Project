import { apiFetch } from "@/app/components/AuthContext";

import {
    getPendingCheckins,
    removePendingCheckin,
    updatePendingCheckin,
    type PendingCheckin,
} from "@/app/lib/offlineStorage";

let syncInProgress = false;

export async function syncPendingCheckins(): Promise<void> {
    // Prevent concurrent synchronization attempts in this page.
    if (syncInProgress || !navigator.onLine) {
        return;
    }

    syncInProgress = true;

    try {
        const pending = await getPendingCheckins();

        for (const entry of pending) {
            if (!navigator.onLine) {
                break;
            }

            await submitPendingCheckin(entry);
        }
    } finally {
        syncInProgress = false;
    }
}

async function submitPendingCheckin(
    entry: PendingCheckin
): Promise<void> {
    try {
        const response = await apiFetch(
            `${process.env.NEXT_PUBLIC_API_BASE_URL}/checkins/`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(entry.payload),
            }
        );


        if (response.ok) {
            // The server accepted the check-in.
            await removePendingCheckin(entry.id);
            return;
        }

        let responseData: {
            detail?: string;
            message?: string;
        } = {};

        try {
            responseData = await response.json();
        } catch {
            // The response may not contain valid JSON.
        }

        const errorMessage = responseData.detail ?? "";

        // The backend confirms that a check-in already exists.
        // Remove this queued submission instead of retrying forever.
        if (
            response.status === 400 &&
            errorMessage.toLowerCase().includes("already checked in")
        ) {
            await removePendingCheckin(entry.id);
            return;
        }


        // Retry later for server errors and rate limiting.
        if (response.status >= 500 || response.status === 429 || response.status === 404) {
            await updatePendingCheckin({
                ...entry,
                attempts: entry.attempts + 1,
                lastError: `Server returned HTTP ${response.status}`,
            });

            return;
        }

        // Retain other rejected submissions for inspection.
        await updatePendingCheckin({
            ...entry,
            attempts: entry.attempts + 1,
            lastError:
                errorMessage ||
                `Submission rejected: HTTP ${response.status}`,
        });
    } catch {
        // Keep the queued entry if the request fails unexpectedly.
        await updatePendingCheckin({
            ...entry,
            attempts: entry.attempts + 1,
            lastError: "Network or request error; submission will be retried.",
        });
    }
}