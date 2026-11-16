'use client'

import { useRouter } from 'next/navigation'
import { useAuth } from '@/app/components/AuthContext'
import { useFeedback } from '@/app/components/FeedbackContext'

type NavItem = {
  label: string
  path: string
}

const publicItems: NavItem[] = [
  { label: 'Login', path: '/login' },
  { label: 'Register', path: '/register' },
  { label: 'Active sessions', path: '/sessions' },
]

const studentItems: NavItem[] = [
  { label: 'Profile', path: '/profile' },
  { label: 'Checkins', path: '/checkins' },
  { label: 'Sessions', path: '/sessions' },
  { label: 'Courses', path: '/courses' },
  { label: 'Devices', path: '/devices' },
  { label: 'My enrollments', path: '/my-enrollments' },
]

const taItems: NavItem[] = [
  { label: 'Profile', path: '/profile' },
  { label: 'Checkins', path: '/checkins' },
  { label: 'Sessions', path: '/sessions' },
  { label: 'Courses', path: '/courses' },
  { label: 'Stats', path: '/stats' },
  { label: 'Devices', path: '/devices' },
  { label: 'Enrollments', path: '/enrollments' },
]

const instructorItems: NavItem[] = [
  ...taItems,
  { label: 'Find user', path: '/find-user' },
]

const adminItems: NavItem[] = [
  ...instructorItems,
  { label: 'Audit', path: '/audit' },
]

export default function NavigationDrawer() {
  const router = useRouter()
  const { user, authReady, logout } = useAuth()
  const { setMsg } = useFeedback()

  if (!authReady) {
    return null
  }

  let items: NavItem[]

  if (!user) {
    items = publicItems
  } else {
    switch (user.role) {
      case 'student':
        items = studentItems
        break
      case 'ta':
        items = taItems
        break
      case 'instructor':
        items = instructorItems
        break
      case 'admin':
        items = adminItems
        break
      default:
        items = publicItems
    }
  }

  function handleLogout() {
    logout()
    router.push('/')
  }

  return (
    <aside className="w-full border-b border-gray-200 bg-white p-4 md:min-h-screen md:w-60 md:border-b-0 md:border-r">
      <div className="mb-6">
        <h2 className="text-xl font-bold text-gray-900">SAIV</h2>

        {user && (
          <div className="mt-2">
            <p className="text-sm font-medium text-gray-800">
              {user.full_name}
            </p>
            <p className="text-xs capitalize text-gray-500">
              {user.role}
            </p>
          </div>
        )}
      </div>

      <nav className="flex flex-wrap gap-2 md:flex-col">
        {items.map((item) => (
          <button
            key={item.path}
            type="button"
            onClick={() => {
              setMsg("", true);
              router.push(item.path)}}
            className="rounded-md px-4 py-2 text-left text-sm text-gray-700 transition hover:bg-gray-100 hover:text-gray-950"
          >
            {item.label}
          </button>
        ))}

        {user && (
          <button
            type="button"
            onClick={handleLogout}
            className="rounded-md px-4 py-2 text-left text-sm text-red-700 transition hover:bg-red-50"
          >
            Logout
          </button>
        )}
      </nav>
    </aside>
  )
}