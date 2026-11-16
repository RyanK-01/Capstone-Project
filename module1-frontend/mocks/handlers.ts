import { http, HttpResponse } from "msw";

export const handlers = [
  //simulate response from the endpoint api/v1/sessions/my-sessions
  http.get(
    `${process.env.NEXT_PUBLIC_API_BASE_URL}/sessions`,
    () => {
      return HttpResponse.json({
        items: [
          {
            id: "8f3c2a71-6d4e-4b9f-a2c1-17e5d8b90432",
            course_id: "2a7d91c4-53e8-4f16-bb72-9c4e1d6a8053",
            course_code: "SC4055",
            course_name: "Introduction to Quantum Computing",
            instructor_id: "c91e7b52-8a34-4d6f-b215-53e9a7c18420",
            name: "Lecture 6: Quantum Algorithms",
            session_type: "lecture",
            status: "active",
            scheduled_start: "2026-09-04T14:00:00Z",
            scheduled_end: "2026-09-04T16:00:00Z",
            checkin_opens_at: "2026-09-04T13:45:00Z",
            checkin_closes_at: "2026-09-04T14:30:00Z",
            venue_name: "NTU LT1",
            total_enrolled: 42,
            checked_in_count: 31
          },
          {
            id: "4b9e6c13-2f75-48a1-9d63-85c7e2041b96",
            course_id: "71d4a832-9c56-4e17-b281-63f0a9d52487",
            course_code: "SC3099",
            course_name: "Software Engineering",
            instructor_id: "e52a9c74-1d38-4f65-b907-28c3e6a15491",
            name: "Tutorial 3: Requirements Engineering",
            session_type: "tutorial",
            status: "upcoming",
            scheduled_start: "2026-09-05T10:00:00Z",
            scheduled_end: "2026-09-05T12:00:00Z",
            checkin_opens_at: "2026-09-05T09:45:00Z",
            checkin_closes_at: "2026-09-05T10:30:00Z",
            venue_name: "N4.2-01-03",
            total_enrolled: 35,
            checked_in_count: 0
          },
          {
            id: "c73d1f58-9a26-4e82-b514-67f0a3d92845",
            course_id: "5e82b471-36c9-4a17-8d52-b904c6f17328",
            course_code: "SC4064",
            course_name: "GPU Computing",
            instructor_id: "a61f8c35-27d4-49e0-b752-93c4d8165a20",
            name: "Lab 4: CUDA Optimisation",
            session_type: "lab",
            status: "completed",
            scheduled_start: "2026-09-03T09:00:00Z",
            scheduled_end: "2026-09-03T11:00:00Z",
            checkin_opens_at: "2026-09-03T08:45:00Z",
            checkin_closes_at: "2026-09-03T09:30:00Z",
            venue_name: "SCSE Lab 2",
            total_enrolled: 28,
            checked_in_count: 26
          }
        ],
        total: 3,
        limit: 50,
        offset: 0
      });
    }
  ),

  http.get(
    `${process.env.NEXT_PUBLIC_API_BASE_URL}/sessions/my-sessions`,
    () => {
      return HttpResponse.json([
        {
          id: "8f3c2a71-6d4e-4b9f-a2c1-17e5d8b90432",
          course_id: "2a7d91c4-53e8-4f16-bb72-9c4e1d6a8053",
          course_code: "SC4055",
          name: "Lecture 6: Quantum Algorithms",
          status: "active",
          scheduled_start: "2026-09-04T14:00:00Z",
          scheduled_end: "2026-09-04T16:00:00Z",
          checkin_opens_at: "2026-09-04T13:45:00Z",
          checkin_closes_at: "2026-09-04T14:30:00Z",
          venue_name: "NTU LT1",
        },
        {
          id: "4b9e6c13-2f75-48a1-9d63-85c7e2041b96",
          course_id: "71d4a832-9c56-4e17-b281-63f0a9d52487",
          course_code: "SC3099",
          name: "Tutorial 3: Requirements Engineering",
          status: "upcoming",
          scheduled_start: "2026-09-05T10:00:00Z",
          scheduled_end: "2026-09-05T12:00:00Z",
          checkin_opens_at: "2026-09-05T09:45:00Z",
          checkin_closes_at: "2026-09-05T10:30:00Z",
          venue_name: "N4.2-01-03",
        },
        {
          id: "c73d1f58-9a26-4e82-b514-67f0a3d92845",
          course_id: "5e82b471-36c9-4a17-8d52-b904c6f17328",
          course_code: "SC4064",
          name: "Lab 4: CUDA Optimisation",
          status: "completed",
          scheduled_start: "2026-09-03T09:00:00Z",
          scheduled_end: "2026-09-03T11:00:00Z",
          checkin_opens_at: "2026-09-03T08:45:00Z",
          checkin_closes_at: "2026-09-03T09:30:00Z",
          venue_name: "SCSE Lab 2",
        }
      ]
      );
    }
  ),

  http.get(
    `${process.env.NEXT_PUBLIC_API_BASE_URL}/sessions/active`,
    () => {
      return HttpResponse.json([
        {
          id: "8f3c2a71-6d4e-4b9f-a2c1-17e5d8b90432",
          course_id: "2a7d91c4-53e8-4f16-bb72-9c4e1d6a8053",
          course_code: "SC4055",
          name: "Lecture 6: Quantum Algorithms",
          status: "active",
          scheduled_start: "2026-09-04T14:00:00Z",
          scheduled_end: "2026-09-04T16:00:00Z",
          checkin_opens_at: "2026-09-04T13:45:00Z",
          checkin_closes_at: "2026-09-04T14:30:00Z",
          venue_name: "NTU LT1",
        },
        {
          id: "4b9e6c13-2f75-48a1-9d63-85c7e2041b96",
          course_id: "71d4a832-9c56-4e17-b281-63f0a9d52487",
          course_code: "SC3099",
          name: "Tutorial 3: Requirements Engineering",
          status: "upcoming",
          scheduled_start: "2026-09-05T10:00:00Z",
          scheduled_end: "2026-09-05T12:00:00Z",
          checkin_opens_at: "2026-09-05T09:45:00Z",
          checkin_closes_at: "2026-09-05T10:30:00Z",
          venue_name: "N4.2-01-03",
        },
        {
          id: "c73d1f58-9a26-4e82-b514-67f0a3d92845",
          course_id: "5e82b471-36c9-4a17-8d52-b904c6f17328",
          course_code: "SC4064",
          name: "Lab 4: CUDA Optimisation",
          status: "completed",
          scheduled_start: "2026-09-03T09:00:00Z",
          scheduled_end: "2026-09-03T11:00:00Z",
          checkin_opens_at: "2026-09-03T08:45:00Z",
          checkin_closes_at: "2026-09-03T09:30:00Z",
          venue_name: "SCSE Lab 2",
        }
      ]
      );
    }
  ),

  http.get(
    `${process.env.NEXT_PUBLIC_API_BASE_URL}/sessions/:id`,
    () => {
      return HttpResponse.json({
        id: "uuid",
        course_id: "uuid",
        instructor_id: "uuid",
        name: "Lecture 5: Neural Networks",
        session_type: "lecture",
        status: "active",
        scheduled_start: "2024-01-15T14:00:00Z",
        scheduled_end: "2024-01-15T16:00:00Z",
        checkin_opens_at: "2024-01-15T13:45:00Z",
        checkin_closes_at: "2024-01-15T14:30:00Z",
        venue_latitude: 1.3483,
        venue_longitude: 103.6831,
        venue_name: "NTU LT1",
        geofence_radius_meters: 100.0,
        require_liveness_check: true,
        require_face_match: false,
        risk_threshold: 0.5,
        qr_code_enabled: true,
        created_at: "2024-01-14T10:00:00Z"
      });
    }
  ),

  http.post(
    `${process.env.NEXT_PUBLIC_API_BASE_URL}/checkins`,
    () => {
      return HttpResponse.json({
        id: "uuid",
        session_id: "uuid",
        student_id: "uuid",
        status: "approved",  // pending|approved|flagged|rejected
        checked_in_at: "2024-01-15T14:05:00Z",
        latitude: 1.3483,
        longitude: 103.6831,
        distance_from_venue_meters: 45.2,
        liveness_passed: true,
        liveness_score: 0.92,
        risk_score: 0.15,
        risk_factors: [
          { type: "device_unknown", weight: 0.15}
        ]
      });
    }
  ),


  http.get(
    `${process.env.NEXT_PUBLIC_API_BASE_URL}/checkins`,
    () => {
      return HttpResponse.json({
        items: [
          {
            id: "uuid",
            session_id: "uuid",
            session_name: "Lecture 5",
            student_id: "uuid",
            student_name: "John Doe",
            student_email: "john@example.com",
            status: "approved",
            checked_in_at: "2024-01-15T14:05:00Z",
            distance_from_venue_meters: 45.2,
            risk_score: 0.15,
            liveness_passed: true
          }
        ],
        total: 500,
        limit: 50,
        offset: 0
      });
    }
  ),

  http.get(
    `${process.env.NEXT_PUBLIC_API_BASE_URL}/checkins/my-checkins`,
    () => {
      return HttpResponse.json([
        {
          id: "uuid",
          session_id: "uuid",
          session_name: "Lecture 5: Neural Networks",
          course_code: "CS6101",
          status: "approved",
          checked_in_at: "2024-01-15T14:05:00Z",
          risk_score: 0.15
        }
      ]);
    }
  ),

  http.get(
    `${process.env.NEXT_PUBLIC_API_BASE_URL}/checkins/session/:id`,
    () => {
      return HttpResponse.json([
        {
          id: "uuid",
          student_id: "uuid",
          student_name: "John Doe",
          student_email: "john@example.com",
          status: "approved",
          checked_in_at: "2024-01-15T14:05:00Z",
          distance_from_venue_meters: 45.2,
          risk_score: 0.15,
          risk_factors: [],
          liveness_passed: true,
          device_trusted: true
        }
      ]);
    }
  ),

  http.get(
    `${process.env.NEXT_PUBLIC_API_BASE_URL}/checkins/:id`,
    () => {
      return HttpResponse.json({
        id: "chk_7f3a2b1c-9d8e-4f6a-a5b2-1c3d4e5f6789",
        session_id: "sess_123e4567-e89b-12d3-a456-426614174000",
        student_id: "usr_223e4567-e89b-12d3-a456-426614174001",
        device_id: "dev_323e4567-e89b-12d3-a456-426614174002",

        status: "flagged",

        checked_in_at: "2026-10-16T09:30:00+08:00",
        verified_at: null,

        location_accuracy_meters: 85.5,
        distance_from_venue_meters: 420.3,

        liveness_passed: true,
        liveness_score: 0.92,
        liveness_challenge_type: "blink",

        face_match_passed: true,
        face_match_score: 0.87,

        risk_score: 0.68,

        risk_factors: [
          {
            signal_type: "geo_out_of_bounds",
            severity: "high",
            confidence: 0.95,
            details: JSON.stringify({
              expected_radius_meters: 100,
              actual_distance_meters: 420.3,
              latitude: 1.3521,
              longitude: 103.8198,
            }),
            weight: 0.3,
          },
          {
            signal_type: "geo_accuracy_low",
            severity: "medium",
            confidence: 0.88,
            details: JSON.stringify({
              reported_accuracy_meters: 85.5,
              maximum_accepted_accuracy_meters: 50,
            }),
            weight: 0.15,
          },
          {
            signal_type: "device_unknown",
            severity: "medium",
            confidence: 0.75,
            details: JSON.stringify({
              device_fingerprint_known: false,
              first_seen: true,
            }),
            weight: 0.2,
          },
          {
            signal_type: "face_match_low_confidence",
            severity: "low",
            confidence: 0.9,
            details: JSON.stringify({
              similarity_score: 0.87,
              minimum_accepted_score: 0.9,
            }),
            weight: 0.1,
          },
        ],

        qr_code_verified: true,

        reviewed_by_id: null,
        reviewed_at: null,
        review_notes: null,

        appeal_reason: null,
        appealed_at: null,
      });
    }
  ),

  http.get(
    `${process.env.NEXT_PUBLIC_API_BASE_URL}/courses`,
    () => {
      return HttpResponse.json({
        items: [
          {
            id: "uuid",
            code: "CS6101",
            name: "Advanced Topics in CS",
            semester: "AY2024-25 Sem 1",
            instructor_id: "uuid",
            instructor_name: "Dr. Smith",
            venue_name: "LT1",
            venue_latitude: 1.3483,
            venue_longitude: 103.6831,
            geofence_radius_meters: 100.0,
            risk_threshold: 0.5,
            is_active: true,
            created_at: "2024-01-10T10:00:00Z"
          }
        ],
        total: 25,
        limit: 50,
        offset: 0
      });
    }
  ),


  http.get(
    `${process.env.NEXT_PUBLIC_API_BASE_URL}/audit`,
    () => {
      return HttpResponse.json({
        items: [
          {
            id: "uuid",
            user_id: "uuid",
            user_email: "student@example.com",
            action: "checkin_attempted",
            resource_type: "checkin",
            resource_id: "uuid",
            ip_address: "192.168.1.1",
            user_agent: "Mozilla/5.0...",
            device_id: "uuid",
            details: {
              session_id: "uuid",
              risk_score: 0.15
            },
            success: true,
            timestamp: "2024-01-15T14:05:00Z"
          }
        ],
        total: 5000,
        limit: 100,
        offset: 0
      });
    }
  ),

  http.get(
    `${process.env.NEXT_PUBLIC_API_BASE_URL}/devices/my-devices`,
    () => {
      return HttpResponse.json([
        {
          id: "uuid",
          device_name: "John's iPhone",
          platform: "ios",
          is_trusted: true,
          trust_score: "high",
          is_active: true,
          first_seen_at: "2024-01-01T10:00:00Z",
          last_seen_at: "2024-01-15T14:05:00Z",
          total_checkins: 25
        }
      ]);
    }
  ),

  http.get(
    `${process.env.NEXT_PUBLIC_API_BASE_URL}/users/me`,
    () => {
      return HttpResponse.json({
        id: "uuid",
        email: "student@example.com",
        full_name: "John Doe",
        role: "student",
        camera_consent: true,
        geolocation_consent: true,
        face_enrolled: false,
        created_at: "2024-01-15T10:00:00Z"
      });
    }
  ),

  http.post(
    `${process.env.NEXT_PUBLIC_API_BASE_URL}/users/me`,
    async ({ request }) => {

      const { full_name, camera_consent, geolocation_consent } = await request.json() as {
        full_name: string, camera_consent: boolean, geolocation_consent: boolean
      };

      return HttpResponse.json({
        id: "uuid",
        email: "student@example.com",
        full_name: full_name,
        role: "student",
        camera_consent: camera_consent,
        geolocation_consent: geolocation_consent,
        face_enrolled: false,
        created_at: "2024-01-15T10:00:00Z"
      }, { status: 200 });
    }
  ),

  http.post(
    `${process.env.NEXT_PUBLIC_API_BASE_URL}/users/me/face/enroll`,
    async () => {

      return HttpResponse.json({
        success: true,
        message: "Face enrolled successfully",
        face_enrolled: true,
        quality_score: 0.85
      }, { status: 200 });
    }
  ),

  //simulate response from the endpoint api/v1/auth/register
  http.post(
    `${process.env.NEXT_PUBLIC_API_BASE_URL}/auth/register`,
    async ({ request }) => {

      const { email, password, full_name, role } = await request.json() as {
        email: string, password: string, full_name: string, role: string
      };

      return HttpResponse.json({
        email: email,
        password: password,
        full_name: full_name,
        role: role
      }, { status: 201 });
    }
  ),


  //simulate response from the endpoint api/v1/auth/login
  http.post(
    `${process.env.NEXT_PUBLIC_API_BASE_URL}/auth/login`,
    async ({ request }) => {

      const { password } = await request.json() as {
        email: string, password: string
      };

      let role = "student";

      if (password === "ta" || password === "instructor" || password === "admin") {
        role = password;
      }

      return HttpResponse.json({
        access_token: "AT",
        refresh_token: "RT",
        token_type: "bearer",
        user: {
          id: "USER ID",
          email: "sample@email.com",
          full_name: "John Doe",
          role: role,
          is_active: true,
          created_at: "2024-01-15T10:00:00Z"
        }
      }, { status: 200 });
    }
  )

];