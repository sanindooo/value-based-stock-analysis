---
title: Background Task Lifecycle Management
date: 2026-05-17
category: architecture-patterns
module: full-stack/task-system
problem_type: architecture_pattern
component: background_job
severity: medium
applies_when:
  - Long-running operations need progress feedback (screening 150+ stocks, research generation)
  - Frontend needs to poll and display real-time progress
  - Tasks can be cancelled mid-execution
  - App must recover gracefully from page refreshes during active tasks
tags:
  - background-tasks
  - polling
  - progress-tracking
  - task-context
  - cancellation
  - orphan-recovery
  - concurrent-guard
related_components:
  - service_object
  - frontend_stimulus
  - database
---

# Background Task Lifecycle Management

## Context

Stock screening runs take 30-60 seconds (fetching data for 150+ tickers, scoring, filtering). Research generation takes longer (SEC filing extraction + Claude analysis per stock). These can't block the HTTP request. The app needs a full task lifecycle: create, poll progress, display real-time updates, support cancellation, and recover from page refreshes.

The solution spans three layers: a `TaskStatus` model in Postgres (source of truth), a `BackgroundTasks` executor in FastAPI (runs the work), and a `TaskContext` in React (polls and distributes state to the UI).

## Guidance

### Backend: Task State Machine

Tasks flow through states: `pending` → `running` → `completed|failed|cancelled`

```python
# Backend task model (task.py)
class TaskStatus(Base):
    __tablename__ = "task_status"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    result_id: Mapped[int | None] = mapped_column(Integer)
    progress: Mapped[str | None] = mapped_column(String(50))
    progress_data: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

### Backend: Concurrent Guard

Only one screening task at a time. Check before creating:

```python
@router.post("/run")
async def start_screening_run(body, background_tasks, db):
    active = await db.execute(
        select(TaskStatus).where(
            TaskStatus.task_type == "screening",
            TaskStatus.status.in_(["pending", "running"]),
        )
    )
    if active.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="A screen is already running.")

    task = TaskStatus(task_type="screening", status="pending", progress="queued")
    db.add(task)
    await db.commit()
    await db.refresh(task)

    background_tasks.add_task(_run_screening_task, task_id=task.id, ...)
    return {"task_id": task.id, "run_id": 0}  # run_id populated by background task
```

### Backend: Progress Updates from Background Task

The background task updates `progress_data` JSON as it works, giving the frontend granular progress:

```python
async def _run_screening_task(task_id, filter_config, max_examined, max_matches):
    async with async_session() as db:
        task = (await db.execute(select(TaskStatus).where(TaskStatus.id == task_id))).scalar_one()
        task.status = "running"
        task.progress_data = {"stage": "fetching", "stocks_examined": 0, "total_stocks": N}
        await db.commit()

        # ... fetch and score stocks, updating progress_data periodically ...

        task.status = "completed"
        task.result_id = run.id
        task.completed_at = datetime.now(timezone.utc)
        await db.commit()
```

### Backend: Cancellation Support

Cancellation is cooperative — the background task checks a flag between batches:

```python
@router.post("/tasks/{task_id}/cancel")
async def cancel_screening_task(task_id, db):
    task = (await db.execute(select(TaskStatus).where(TaskStatus.id == task_id))).scalar_one_or_none()
    if task.status in ("completed", "failed", "cancelled"):
        return task  # No-op
    task.status = "cancelling"
    await db.commit()
    return task

# In the background task:
async def cancel_check():
    async with async_session() as check_db:
        t = (await check_db.execute(select(TaskStatus).where(TaskStatus.id == task_id))).scalar_one()
        return t.status == "cancelling"

# Pass cancel_check to batch operations
results = await fmp.fetch_and_cache_batch(client, db, tickers, cancel_check=cancel_check)
```

### Frontend: TaskContext with Polling

A React context provides task state to the entire app. It polls active tasks every 3 seconds and auto-stops when all tasks complete:

```typescript
export function TaskProvider({ children }) {
  const [tasks, setTasks] = useState<Map<number, TaskState>>(new Map())
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const registeredIds = useRef<Set<number>>(new Set())

  const pollTasks = useCallback(async () => {
    const activeIds = Array.from(registeredIds.current)
    if (activeIds.length === 0) return

    for (const taskId of activeIds) {
      try {
        const data = await apiFetch(`/screening/tasks/${taskId}/status`)
        setTasks((prev) => { /* update map */ })
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
    if (!pollingRef.current) {
      pollingRef.current = setInterval(pollTasks, 3000)
      pollTasks()  // Immediate first poll
    }
  }, [pollTasks])
  // ...
}
```

### Frontend: Orphan Recovery on Mount

When the user refreshes the page mid-task, the TaskContext recovers by checking for active tasks on mount:

```typescript
useEffect(() => {
  async function recover() {
    try {
      const active = await apiFetch<TaskApiResponse[]>("/screening/tasks?status=running,pending,cancelling")
      for (const task of active) {
        registerTask(task.id)
      }
    } catch {
      // No active tasks or endpoint unavailable
    }
  }
  recover()
  return () => { /* cleanup interval */ }
}, [registerTask])
```

### Frontend: Derived State

Components consume `activeScreeningTask` and `lastCompletedTask` without polling logic:

```typescript
const activeScreeningTask = Array.from(tasks.values()).find(
  (t) => ["running", "pending", "cancelling"].includes(t.status)
) ?? null

const lastCompletedTask = Array.from(tasks.values()).find(
  (t) => ["completed", "failed", "cancelled"].includes(t.status)
) ?? null
```

## Why This Matters

**User confidence**: Real-time progress (stocks examined, matches found, stage) tells users the app is working, not frozen. Without it, a 60-second screening run feels broken.

**Reliability**: The concurrent guard prevents duplicate runs that would exhaust API quota. Cancellation prevents wasted API calls when the user changes their mind.

**Resilience**: Orphan recovery means page refreshes don't lose track of running tasks. The polling interval auto-starts on recovery and auto-stops on completion.

**Simplicity**: All task state lives in one Postgres table. The frontend polls a single endpoint per task. No WebSockets, no SSE, no pub/sub infrastructure.

## When to Apply

- Operations take >5 seconds (long enough for users to wonder "is it working?")
- Progress can be meaningfully reported (stages, counts, percentages)
- Users need ability to cancel mid-operation
- The app must survive page refreshes during active work

**Simpler alternatives for simpler cases:**
- Operations <5s: just show a spinner, no task system needed
- No cancellation needed: fire-and-forget with a completion webhook
- Real-time updates critical: WebSockets/SSE instead of polling

## Examples

The complete flow for a screening run:

1. User clicks "Run Screen" → POST creates TaskStatus, returns `task_id`
2. `registerTask(taskId)` starts 3s polling interval
3. Background task updates `progress_data` as it fetches/scores
4. Frontend renders `ProgressPanel` from `activeScreeningTask.progress_data`
5. User can cancel → POST sets status to "cancelling" → background task checks and stops
6. Task completes → `result_id` populated → frontend detects terminal state, stops polling

## Related

- [[external-api-client-architecture-2026-05-17]] — the batch operations that run inside background tasks
- `stock-analyzer/frontend/src/contexts/TaskContext.tsx`: Frontend polling implementation
- `stock-analyzer/backend/app/models/task.py`: Task state model
- `stock-analyzer/backend/app/api/screening.py`: Background task orchestration
- Commit `aaa9184`: progress_data, task_id, orphan recovery, concurrent guard
- Commit `aec8687`: Cancel support with incremental saves
