import type { Metadata } from 'next'
import './globals.css'
import MSWProvider from './MSWProvider'
import { AuthProvider } from '@/app/components/AuthContext'
import NavigationDrawer from '@/app/components/NavigationDrawer'
import 'leaflet/dist/leaflet.css'
import { FeedbackProvider } from '@/app/components/FeedbackContext'
import CheckinSyncProvider from '@/app/components/CheckinSyncProvider'
import RegisterServiceWorker from '@/app/components/RegisterServiceWorker'

export const metadata: Metadata = {
  title: 'SAIV - Secure Attendance System',
  description: 'Student check-in interface with liveness detection',
  manifest: '/manifest.webmanifest',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <MSWProvider>
          <AuthProvider>
            <FeedbackProvider>
              <RegisterServiceWorker />
              <CheckinSyncProvider />

              <div className="flex min-h-screen flex-col md:flex-row">
                <NavigationDrawer />
                <main className="min-w-0 flex-1 p-4">
                  {children}
                </main>
              </div>
            </FeedbackProvider>
          </AuthProvider>
        </MSWProvider>
      </body>
    </html>
  )
}
