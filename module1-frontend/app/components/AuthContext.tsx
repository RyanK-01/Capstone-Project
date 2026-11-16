'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react'

// --------------------------------------------------
// Types
// --------------------------------------------------

export type UserRole = 'student' | 'ta' | 'instructor' | 'admin'

export type User = {
  id: string
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  created_at: string
}

type AuthContextType = {
  user: User | null
  authReady: boolean
  login: (user: User, accessToken: string) => void
  logout: () => void
  isAuthenticated: () => boolean
}

type RefreshResponse = {
  access_token?: string
  token_type?: string
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

const AUTH_CHANGE_EVENT = 'saiv:auth-changed'

const VALID_ROLES: UserRole[] = [
  'student',
  'ta',
  'instructor',
  'admin',
]

// --------------------------------------------------
// Shared authentication helpers
// --------------------------------------------------

function notifyAuthChanged() {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(AUTH_CHANGE_EVENT))
  }
}

function readStoredUser(): User | null {
  if (typeof window === 'undefined') {
    return null
  }

  try {
    const storedUser = sessionStorage.getItem('user')

    if (!storedUser) {
      return null
    }

    const parsed: unknown = JSON.parse(storedUser)

    if (
      typeof parsed !== 'object' ||
      parsed === null ||
      !('id' in parsed) ||
      typeof parsed.id !== 'string' ||
      !('role' in parsed) ||
      typeof parsed.role !== 'string' ||
      !VALID_ROLES.includes(parsed.role as UserRole)
    ) {
      return null
    }

    return parsed as User
  } catch {
    return null
  }
}

function clearLocalAuth() {
  if (typeof window === 'undefined') return

  sessionStorage.removeItem('user')
  sessionStorage.removeItem('access_token')

  // Clear the HttpOnly refresh-token cookie through the server.
  void fetch('/api/refresh', {
    method: 'DELETE',
    credentials: 'same-origin',
  }).catch((error) => {
    console.error('Failed to clear refresh-token cookie:', error)
  })

  notifyAuthChanged()
}

/**
 * Reports whether a user is recorded as logged in on this client.
 *
 * This does not validate the access token with the backend.
 */
export function isAuthenticated(): boolean {
  return readStoredUser() !== null
}

// --------------------------------------------------
// Authenticated API fetch
// --------------------------------------------------



/**
 * Makes an authenticated request.
 *
 * Reads the access token from sessionStorage, attaches it as a Bearer
 * token, and on HTTP 401 calls /api/refresh. If refresh returns HTTP 200
 * with a valid access_token, stores the token and retries once.
 *
 * The caller remains responsible for checking the final response.ok.
 */
export async function apiFetch(url: string, init: RequestInit = {}): Promise<Response> {
  if (typeof window === 'undefined') {
    throw new Error('apiFetch can only be called in the browser.')
  }

  const makeRequest = (token: string | null) => {
    const headers = new Headers(init.headers)

    if (token) {
      headers.set('Authorization', `Bearer ${token}`)
    } else {
      headers.delete('Authorization')
    }

    return fetch(url, {
      ...init,
      headers,
    })
  }

  // First attempt using the latest token from sessionStorage.
  const accessToken = sessionStorage.getItem('access_token')
  const response = await makeRequest(accessToken)

  if (response.status !== 401) {
    return response
  }

  // The original request returned 401. Ask the Next.js route to refresh.
  let refreshResponse: Response

  try {
    refreshResponse = await fetch('/api/refresh', {
      method: 'GET',
      credentials: 'same-origin',
      cache: 'no-store',
    })
  } catch {
    // The refresh endpoint could not be reached.
    return response
  }

  // A 401 from the refresh endpoint means the refresh session is invalid
  // or missing. Reset the local login state.
  if (refreshResponse.status === 401) {
    clearLocalAuth()
    return response
  }

  // Retry only when the refresh endpoint returns exactly HTTP 200.
  if (refreshResponse.status !== 200) {
    return response
  }

  let refreshed: RefreshResponse

  try {
    refreshed = await refreshResponse.json()
  } catch {
    return response
  }

  if (
    typeof refreshed.access_token !== 'string' ||
    refreshed.access_token.length === 0
  ) {
    return response
  }

  // Save the new access token before retrying.
  sessionStorage.setItem('access_token', refreshed.access_token)

  // Retry the original request exactly once with the new token.
  const retryResponse = await makeRequest(refreshed.access_token)

  // If the retry is also unauthorized, do not attempt another refresh.
  if (retryResponse.status === 401) {
    clearLocalAuth()
  }

  return retryResponse
}

// --------------------------------------------------
// React authentication provider
// --------------------------------------------------

export function AuthProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const [user, setUser] = useState<User | null>(null)
  const [authReady, setAuthReady] = useState(false)

  useEffect(() => {
    const syncUser = () => {
      setUser(readStoredUser())
    }

    // Restore authentication state when the app loads.
    syncUser()
    setAuthReady(true)

    // Keep React state synchronized with login/logout/refresh failures.
    window.addEventListener(AUTH_CHANGE_EVENT, syncUser)

    return () => {
      window.removeEventListener(AUTH_CHANGE_EVENT, syncUser)
    }
  }, [])

  const login = useCallback(
    (loggedInUser: User, accessToken: string) => {
      sessionStorage.setItem('user', JSON.stringify(loggedInUser))
      sessionStorage.setItem('access_token', accessToken)

      setUser(loggedInUser)
      notifyAuthChanged()
    },
    [],
  )

  const logout = useCallback(() => {
    clearLocalAuth()
    setUser(null)
  }, [])

  const checkAuthenticated = useCallback(() => {
    return user !== null
  }, [user])

  return (
    <AuthContext.Provider
      value={{
        user,
        authReady,
        login,
        logout,
        isAuthenticated: checkAuthenticated,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider')
  }

  return context
}