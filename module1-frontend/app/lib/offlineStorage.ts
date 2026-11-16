import localForage from "localforage";

export type CheckinPayload = Record<string, unknown> & {
    session_id: string;
};

export type PendingCheckin = {
    id: string;
    payload: CheckinPayload;
    queuedAt: string;
    attempts: number;
    lastError?: string;
};

const checkinQueue = localForage.createInstance({
    name: "SAIV",
    storeName: "pending_checkins",
    description: "Check-ins awaiting server submission",
});

export async function getPendingCheckins(): Promise<PendingCheckin[]> {
    const entries: PendingCheckin[] = [];

    await checkinQueue.iterate<PendingCheckin, void>((value) => {
        entries.push(value);
    });

    return entries.sort(
        (a, b) =>
            new Date(a.queuedAt).getTime() -
            new Date(b.queuedAt).getTime()
    );
}

export async function queueCheckin(
    payload: CheckinPayload
): Promise<PendingCheckin | null> {
    const sessionId = payload.session_id;

    if (!sessionId) {
        throw new Error("Cannot queue a check-in without a session ID.");
    }

    const existingEntry = await checkinQueue.getItem(sessionId);

    if (existingEntry) {
        return null;
    }

    // Use session_id as the unique queue key.
    const entry: PendingCheckin = {
        id: sessionId,
        payload,
        queuedAt: new Date().toISOString(),
        attempts: 0,
    };


    await checkinQueue.setItem(sessionId, entry);

    return entry;
}

export async function updatePendingCheckin(
    entry: PendingCheckin
): Promise<void> {
    await checkinQueue.setItem(entry.id, entry);
}

export async function removePendingCheckin(id: string): Promise<void> {
    await checkinQueue.removeItem(id);
}

export async function isPending(session_id: string): Promise<boolean> {
    const existingEntry = await checkinQueue.getItem(session_id);

    return(existingEntry === null)

}