'use client'

import {
  createContext,
  useCallback,
  useContext,
  useState,
} from 'react'

type FeedbackContextType = {
  setMsg: (message: string, fail: boolean) => void
}

type Feedback = {
  message: string
  fail: boolean
} | null

const FeedbackContext = createContext<FeedbackContextType | undefined>(
  undefined,
)

export function FeedbackProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const [feedback, setFeedback] = useState<Feedback>(null)

  const setMsg = useCallback((message: string, fail: boolean) => {
    setFeedback(message ? { message, fail } : null)
  }, [])

  return (
    <FeedbackContext.Provider value={{ setMsg }}>
      {children}

      {feedback && (
        <button
          onClick={() => setFeedback(null)}
          className={`fixed right-4 top-4 z-50 max-w-md rounded-md p-3 text-sm shadow-md ${feedback.fail
            ? 'bg-red-100 text-red-700'
            : 'bg-green-300 text-green-800'
            }`}
          role={feedback.fail ? 'alert' : 'status'}
          aria-live={feedback.fail ? 'assertive' : 'polite'}
        >
          {feedback.message}
        </button>
      )}

      {!navigator.onLine && (
        <div className='w-full bg-blue-400'>
          <button
            className="absolute left-1/2 -translate-x-1/2 bottom-4 z-50 max-w-md rounded-md p-3 text-sm text-black shadow-md bg-yellow-500"
            role={'alert'}
            aria-live={'assertive'}
          >
            ⓘ The server is currently unreachable. Some features may be limited.
          </button>
        </div>
      )}
    </FeedbackContext.Provider>
  )
}

export function useFeedback() {
  const context = useContext(FeedbackContext)

  if (!context) {
    throw new Error('useFeedback must be used inside FeedbackProvider')
  }

  return context
}