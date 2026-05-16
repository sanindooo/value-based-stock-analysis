"use client"

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react"
import { apiFetch } from "@/lib/api"

export interface ProgressData {
  stage: string
  stocks_examined: number
  matches_found: number
  total_stocks: number
  log_entries: { message: string }[]
}

export interface TaskState {
  id: number
  status: string
  progress: string | null
  progress_data: ProgressData | null
  result_id: number | null
  created_at: string | null
  error_message: string | null
}

interface TaskContextValue {
  tasks: Map<number, TaskState>
  registerTask: (taskId: number) => void
  activeScreeningTask: TaskState | null
}

const TaskContext = createContext<TaskContextValue>({
  tasks: new Map(),
  registerTask: () => {},
  activeScreeningTask: null,
})

export function useTaskContext() {
  return useContext(TaskContext)
}

interface TaskApiResponse {
  id: number
  task_type: string
  status: string
  progress: string | null
  progress_data: ProgressData | null
  result_id: number | null
  created_at: string | null
  error_message: string | null
}

export function TaskProvider({ children }: { children: React.ReactNode }) {
  const [tasks, setTasks] = useState<Map<number, TaskState>>(new Map())
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const registeredIds = useRef<Set<number>>(new Set())

  const pollTasks = useCallback(async () => {
    const activeIds = Array.from(registeredIds.current)
    if (activeIds.length === 0) return

    for (const taskId of activeIds) {
      try {
        const data = await apiFetch<TaskApiResponse>(`/screening/tasks/${taskId}/status`)
        setTasks((prev) => {
          const next = new Map(prev)
          next.set(taskId, {
            id: data.id,
            status: data.status,
            progress: data.progress,
            progress_data: data.progress_data,
            result_id: data.result_id,
            created_at: data.created_at,
            error_message: data.error_message,
          })
          return next
        })

        if (["completed", "failed", "cancelled"].includes(data.status)) {
          registeredIds.current.delete(taskId)
        }
      } catch {
        // Retain last-known state on poll failure
      }
    }

    if (registeredIds.current.size === 0 && pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const registerTask = useCallback((taskId: number) => {
    registeredIds.current.add(taskId)
    setTasks((prev) => {
      if (prev.has(taskId)) return prev
      const next = new Map(prev)
      next.set(taskId, {
        id: taskId,
        status: "pending",
        progress: null,
        progress_data: null,
        result_id: null,
        created_at: null,
        error_message: null,
      })
      return next
    })

    if (!pollingRef.current) {
      pollingRef.current = setInterval(pollTasks, 3000)
      pollTasks()
    }
  }, [pollTasks])

  // Cold-start recovery: check for active screening tasks on mount
  useEffect(() => {
    async function recover() {
      try {
        const active = await apiFetch<TaskApiResponse[]>("/screening/tasks?status=running,pending")
        for (const task of active) {
          registerTask(task.id)
        }
      } catch {
        // No active tasks or endpoint unavailable
      }
    }
    recover()

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
        pollingRef.current = null
      }
    }
  }, [registerTask])

  const activeScreeningTask = Array.from(tasks.values()).find(
    (t) => t.status === "running" || t.status === "pending" || t.status === "cancelling"
  ) ?? null

  return (
    <TaskContext.Provider value={{ tasks, registerTask, activeScreeningTask }}>
      {children}
    </TaskContext.Provider>
  )
}
