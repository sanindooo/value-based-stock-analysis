import type { Metadata } from "next"
import "./globals.css"
import { TaskProvider } from "@/contexts/TaskContext"
import NavBar from "@/components/NavBar"
import { Toaster } from "sonner"

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
          <NavBar />
          <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">{children}</main>
          <Toaster position="bottom-right" richColors closeButton />
        </TaskProvider>
      </body>
    </html>
  )
}
