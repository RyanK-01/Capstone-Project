/**
 * SAIV Student Frontend - Module 1
 *
 * This is the skeleton implementation for the Student Frontend PWA.
 * Students must implement the check-in interface with camera access,
 * geolocation, and device binding.
 */
"use client";
import { useRouter } from "next/navigation";
import { useState, useEffect } from 'react';
import { User, useAuth } from '@/app/components/AuthContext';

export default function Home() {
  const router = useRouter();
  const [role, setRole] = useState("none");
  const [authReady, setAuthReady] = useState(false);
  const [welcomeText, setWelcomeText] = useState("");
  const { logout } = useAuth();
  //router.push('/login');
  useEffect(() => {
    try {
      const storedUser = sessionStorage.getItem('user');

      if (storedUser) {
        try {
          const parsedUser = JSON.parse(storedUser) as User;

          if (
            parsedUser &&
            typeof parsedUser.role === 'string' &&
            typeof parsedUser.full_name === 'string'
          ) {
            setRole(parsedUser.role);
            setWelcomeText(" back, " + parsedUser.full_name);
          }
        } catch {
          console.error('Could not parse the stored user.');
        }
      }
    } finally {
      setAuthReady(true);
    }
  }, [authReady]);

  function logoutButton() {
    logout();
    setWelcomeText("");
    setRole("none");
    setAuthReady(false);
  }

  return (
    <main className="flex flex-col w-full min-h-screen items-center justify-center bg-gray-100">

      <div className="flex flex-col w-full max-w-lg shadow-2xl p-10 space-y-6 rounded-lg">

        <h1 className="text-4xl font-bold mb-8 w-full text-center">
          Welcome{welcomeText}
        </h1>

        {authReady && role === "none" && (
          <div className="flex flex-col w-full space-y-6">
            <button
              type="button"
              onClick={() => router.push('/login')}
              className="bg-blue-600 text-2xl font-bold p-4 rounded-md text-white hover:text-black hover:bg-yellow-400">
              Login
            </button>

            <button
              type="button"
              onClick={() => router.push('/register')}
              className="bg-blue-600 text-2xl font-bold p-4 rounded-md text-white hover:text-black hover:bg-yellow-400">
              Register
            </button>

            <button
              type="button"
              onClick={() => router.push('/sessions')}
              className="bg-blue-600 text-2xl font-bold p-4 rounded-md text-white hover:text-black hover:bg-yellow-400">
              Active sessions
            </button>
        </div>
        )}

        {authReady && role !== "none" && (
          <div className="grid grid-cols-1 sm:grid-cols-2 w-full gap-y-6 gap-x-4">
            <button
              type="button"
              onClick={() => router.push('/profile')}
              className="bg-blue-600 text-2xl font-bold p-4 rounded-md text-white hover:text-black hover:bg-yellow-400">
              Profile
            </button>

            <button
              type="button"
              onClick={() => router.push('/checkins')}
              className="bg-blue-600 text-2xl font-bold p-4 rounded-md text-white hover:text-black hover:bg-yellow-400">
              Checkins
            </button>

            <button
              type="button"
              onClick={() => router.push('/sessions')}
              className="bg-blue-600 text-2xl font-bold p-4 rounded-md text-white hover:text-black hover:bg-yellow-400">
              Sessions
            </button>

            {authReady && (role === "instructor" || role === "admin") && ( 
              <button
                type="button"
                onClick={() => router.push('/find-user')}
                className="bg-blue-600 text-2xl font-bold p-4 rounded-md text-white hover:text-black hover:bg-yellow-400">
                Find user
              </button>
            )}

            <button
              type="button"
              onClick={() => router.push('/courses')}
              className="bg-blue-600 text-2xl font-bold p-4 rounded-md text-white hover:text-black hover:bg-yellow-400">
              Courses
            </button>

            {authReady && (role === "ta" || role === "instructor" || role === "admin") && ( 
              <button
                type="button"
                onClick={() => router.push('/stats')}
                className="bg-blue-600 text-2xl font-bold p-4 rounded-md text-white hover:text-black hover:bg-yellow-400">
                Dashboard
              </button>
            )}

            <button
              type="button"
              onClick={() => router.push('/devices')}
              className="bg-blue-600 text-2xl font-bold p-4 rounded-md text-white hover:text-black hover:bg-yellow-400">
              My devices
            </button>

            {authReady && (role === "ta" || role === "instructor" || role === "admin") && ( 
              <button
                type="button"
                onClick={() => router.push('/enrollments')}
                className="bg-blue-600 text-2xl font-bold p-4 rounded-md text-white hover:text-black hover:bg-yellow-400">
                Enrollments
              </button>
            )}

            {authReady && role === "student" && ( 
              <button
                type="button"
                onClick={() => router.push('/my-enrollments')}
                className="bg-blue-600 text-2xl font-bold p-4 rounded-md text-white hover:text-black hover:bg-yellow-400">
                My enrollments
              </button>
            )}

            {authReady && (role === "admin") && ( 
              <button
                type="button"
                onClick={() => router.push('/audit')}
                className="bg-blue-600 text-2xl font-bold p-4 rounded-md text-white hover:text-black hover:bg-yellow-400">
                Audit
              </button>
            )}

            <button
              type="button"
              onClick={() => logoutButton()}
              className="bg-blue-600 text-2xl font-bold p-4 rounded-md text-white hover:text-black hover:bg-yellow-400">
              Log out
            </button>

        </div>
        )}

      </div>



      {/* ================================================================== */}
      {/* TODO: Implement the following features                             */}
      {/* ================================================================== */}

      {/* ------------------------------------------------------------------ */}
      {/* Authentication                                                     */}
      {/* ------------------------------------------------------------------ */}
      {/* - Login form with email/password                                   */}
      {/* - Registration form                                                */}
      {/* - JWT token storage (secure, HttpOnly where possible)              */}
      {/* - Auto-refresh token logic                                         */}

      {/* ------------------------------------------------------------------ */}
      {/* Camera Access                                                      */}
      {/* ------------------------------------------------------------------ */}
      {/* - WebRTC camera stream                                             */}
      {/* - Liveness challenge UI (blink, head turn prompts)                 */}
      {/* - Frame capture for face verification                              */}
      {/* - Consent flow before camera access                                */}

      {/* ------------------------------------------------------------------ */}
      {/* Geolocation                                                        */}
      {/* ------------------------------------------------------------------ */}
      {/* - Geolocation API integration                                      */}
      {/* - Explicit consent before location access                          */}
      {/* - GPS coordinates sent with check-in                               */}
      {/* - Error handling for denied permissions                            */}

      {/* ------------------------------------------------------------------ */}
      {/* Device Binding                                                     */}
      {/* ------------------------------------------------------------------ */}
      {/* - ECDSA key pair generation (Web Crypto API)                       */}
      {/* - Public key rotation on each session                              */}
      {/* - Device fingerprinting                                            */}
      {/* - Secure key storage                                               */}

      {/* ------------------------------------------------------------------ */}
      {/* PWA Features                                                       */}
      {/* ------------------------------------------------------------------ */}
      {/* - Service worker for offline support                               */}
      {/* - PWA manifest                                                     */}
      {/* - Offline check-in queue with sync                                 */}
      {/* - LocalForage for persistent storage                               */}

      {/* ------------------------------------------------------------------ */}
      {/* Check-in Flow                                                      */}
      {/* ------------------------------------------------------------------ */}
      {/* 1. Select active session                                           */}
      {/* 2. Grant camera permission (with consent)                          */}
      {/* 3. Complete liveness challenge                                     */}
      {/* 4. Grant location permission (with consent)                        */}
      {/* 5. Submit check-in to backend                                      */}
      {/* 6. Display success/failure with risk score                         */}

    </main>
  );
}
