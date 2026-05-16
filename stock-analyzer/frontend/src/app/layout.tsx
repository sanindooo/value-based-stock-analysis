import type { Metadata } from "next"
import "./globals.css"
import { TaskProvider } from "@/contexts/TaskContext"

export const metadata: Metadata = {
  title: "Stock Analyzer",
  description: "Value investing stock screening and research pipeline",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900">
        <TaskProvider>
          <nav className="border-b border-gray-200 bg-white">
            <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
              <a href="/" className="text-lg font-semibold">
                Stock Analyzer
              </a>
              <div className="flex gap-6 text-sm">
                <a href="/" className="text-gray-600 hover:text-gray-900">
                  Dashboard
                </a>
                <a
                  href="/screening"
                  className="text-gray-600 hover:text-gray-900"
                >
                  Screening
                </a>
                <a
                  href="/research"
                  className="text-gray-600 hover:text-gray-900"
                >
                  Research
                </a>
                <a
                  href="/learn"
                  className="text-gray-600 hover:text-gray-900"
                >
                  Learn
                </a>
                <a
                  href="/settings"
                  className="text-gray-600 hover:text-gray-900"
                >
                  Settings
                </a>
              </div>
            </div>
          </nav>
          <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
        </TaskProvider>
      </body>
    </html>
  )
}
