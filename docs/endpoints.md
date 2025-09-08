# Tamiti Lanes API Endpoints (Django backend)

Base URL: `/api`

Auth: Bearer JWT in `Authorization: Bearer <token>` header. Paginated list responses use `{ count, next, previous, results }`.

## Auth
- POST `/auth/login`
  - Body: `{ email, password }`
  - Returns: `{ access_token, user }`
- POST `/auth/logout` (optional)
- GET `/auth/me` (optional)
  - Returns: `user`

## Users (optional for profile/settings)
- GET `/users/me`
- PATCH `/users/me`

## Tasks
- GET `/tasks`
  - Query: `status`, `domain`, `page`, `page_size`
  - Returns: `PaginatedResponse<Task>`
- POST `/tasks`
  - Body: `Partial<Task>`
  - Returns: `Task`
- GET `/tasks/:id`
  - Returns: `Task`
- PATCH `/tasks/:id`
  - Body: `Partial<Task>`
  - Returns: `Task`
- DELETE `/tasks/:id` (optional; UI currently archives via status)
- POST `/tasks/:id/complete`
  - Returns: `Task` (with `status: done`)
- POST `/tasks/:id/snooze`
  - Body: `{ until: ISO8601 }`
  - Returns: `Task` (server may update scheduling-related fields)

## Schedule / Coach
- POST `/schedule/preview`
  - Body: `{ scope: 'day' | 'week' | 'month', date: ISO8601 | 'YYYY-MM-DD' }`
  - Returns: `SchedulePreview { blocks, conflicts, capacity_usage }`
- POST `/schedule/commit`
  - Body: `{ block_ids: number[] }`
  - Returns: `{ success: boolean }`
- POST `/replan`
  - Body: `{ scope: 'day' | 'week' | 'month', date: ISO8601 | 'YYYY-MM-DD' }`
  - Returns: `SchedulePreview`

## Time Blocks
- GET `/blocks`
  - Query: `date` (YYYY-MM-DD), `scope` ('day' | 'week' | 'month')
  - Returns: `PaginatedResponse<TimeBlock>`
- GET `/blocks/:id`
  - Returns: `TimeBlock`
- PATCH `/blocks/:id`
  - Body: `Partial<TimeBlock>` (e.g., `starts_at`, `ends_at`, `status`)
  - Returns: `TimeBlock`
- POST `/blocks` (optional; usually created by scheduler commit)
- DELETE `/blocks/:id` (optional)

## Calendar Events
- GET `/events`
  - Query: `start`, `end` (ISO8601)
  - Returns: `PaginatedResponse<CalendarEvent>`
- POST `/events`
  - Body: `Partial<CalendarEvent>`
  - Returns: `CalendarEvent`
- GET `/events/:id`
  - Returns: `CalendarEvent`
- PATCH `/events/:id`
  - Body: `Partial<CalendarEvent>`
  - Returns: `CalendarEvent`
- DELETE `/events/:id`

## Goals
- GET `/goals`
  - Returns: `PaginatedResponse<Goal>`
- POST `/goals`
  - Body: `Partial<Goal>`
  - Returns: `Goal`
- GET `/goals/:id`
- PATCH `/goals/:id`
- DELETE `/goals/:id`

## Daily Reviews
- GET `/reviews`
  - Query: `date` (YYYY-MM-DD)
  - Returns: `PaginatedResponse<DailyReview>`
- POST `/reviews`
  - Body: `Partial<DailyReview>`
  - Returns: `DailyReview`
- GET `/reviews/:id`
- PATCH `/reviews/:id`
- DELETE `/reviews/:id`

## Analytics
- GET `/analytics`
  - Query: `period` ('week' | 'month' | 'quarter')
  - Returns: `{ plan_realism, deep_work_min, context_switches, balance_index, estimate_drift }`

## Developer Utilities (optional, for local/demo)
- POST `/dev/reset`
  - Body: `{ latencyMs?, failRatePct?, coachMode?, scope? }`
  - Returns: `{ success: boolean }`

## Advanced/Config (optional but useful for a full planner)
- Availability Templates
  - GET `/availability-templates`
  - POST `/availability-templates`
  - GET `/availability-templates/:id`
  - PATCH `/availability-templates/:id`
  - DELETE `/availability-templates/:id`
- Break Policies
  - GET `/break-policies`
  - POST `/break-policies`
  - GET `/break-policies/:id`
  - PATCH `/break-policies/:id`
  - DELETE `/break-policies/:id`
- Milestones (project-level targets)
  - GET `/milestones`
  - POST `/milestones`
  - GET `/milestones/:id`
  - PATCH `/milestones/:id`
  - DELETE `/milestones/:id`
- Actual Time Tracking (if capturing real usage)
  - GET `/actual-blocks`
  - POST `/actual-blocks`
  - GET `/actual-blocks/:id`
  - PATCH `/actual-blocks/:id`
  - DELETE `/actual-blocks/:id`
- Event Log (audit trail of actions)
  - GET `/events/logs`
  - POST `/events/logs`

---

Notes
- The current frontend expects exactly these paths (no trailing slash) for: `/auth/login`, `/tasks`, `/tasks/:id`, `/tasks/:id/complete`, `/tasks/:id/snooze`, `/blocks`, `/blocks/:id`, `/schedule/preview`, `/schedule/commit`, `/replan`, `/events`, `/goals`, `/reviews`, `/analytics`, `/dev/reset`.
- Use standard Django pagination params `page` and `page_size` to match the UI.
- Entity field shapes follow the interfaces in `lib/types.ts`.

