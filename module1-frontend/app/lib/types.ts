/* Session stuff */
// 'All statuses' must be used for query fields exclusively
export const SESSION_STATUSES = [
    'All statuses',
    'scheduled',
    'active',
    'closed',
    'cancelled',
] as const;

export type SessionStatus = (typeof SESSION_STATUSES)[number];

export const SESSION_TYPES = [
    'lecture',
    'tutorial',
    'lab',
    'exam'
]

export type SessionType = (typeof SESSION_TYPES)[number];

export type SessionDetails = {

    id: string,
    course_id: string,
    instructor_id: string,
    name: string,
    session_type: SessionType,
    status: SessionStatus,
    scheduled_start: string,
    scheduled_end: string,
    checkin_opens_at: string,
    checkin_closes_at: string,
    venue_latitude: number,
    venue_longitude: number,
    venue_name: string,
    geofence_radius_meters: number,
    require_liveness_check: boolean,
    require_face_match: boolean,
    risk_threshold: number,
    qr_code_enabled: boolean,
    created_at: string
}

export type SessionCreate = {
    course_id: string,
    name: string,
    session_type: SessionType,  // lecture|tutorial|lab|exam
    scheduled_start: string,
    scheduled_end: string,
    checkin_opens_at: string,  // Optional, defaults to 15min before start
    checkin_closes_at: string, // Optional, defaults to 30min after start
    venue_latitude: number,  // Optional, uses course default
    venue_longitude: number,
    venue_name: string,
    geofence_radius_meters: number,
    require_liveness_check: boolean,
    require_face_match: boolean,
    risk_threshold: number
}

export type SessionUpdate = {
    status: SessionStatus,
    name: string,
    checkin_closes_at: string

}

/* Checkin stuff */
// 'All statuses' must be used for query fields exclusively
export const CHECKIN_STATUSES = [
    'All statuses',
    'pending',
    'approved',
    'flagged',
    'rejected',
    'appealed'
] as const;

export type CheckinStatus = (typeof CHECKIN_STATUSES)[number];

export type LivenessChallengeType =
    | "blink"
    | "head_turn"
    | "speak";

export type RiskFactor = {
    signal_type: string;
    severity: "low" | "medium" | "high" | "critical";
    confidence: number;
    details: string | Record<string, unknown> | null;
    weight: number;
};

export type Checkin = {
    id: string;
    session_id: string;
    student_id: string;
    device_id: string | null;

    status: CheckinStatus;

    checked_in_at: string;
    verified_at: string | null;

    location_accuracy_meters: number | null;
    distance_from_venue_meters: number | null;

    liveness_passed: boolean | null;
    liveness_score: number | null;
    liveness_challenge_type: LivenessChallengeType | null;

    face_match_passed: boolean | null;
    face_match_score: number | null;

    risk_score: number;
    risk_factors: RiskFactor[] | null;

    qr_code_verified: boolean;

    reviewed_by_id: string | null;
    reviewed_at: string | null;
    review_notes: string | null;

    appeal_reason: string | null;
    appealed_at: string | null;
}



