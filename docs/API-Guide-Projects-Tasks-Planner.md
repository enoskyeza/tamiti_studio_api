# API Guide: Projects, Tasks, and Planner

This guide documents the backend endpoints for Projects, Tasks, and the Planner to help frontend integration. All endpoints are under `/api/` and require JWT auth unless noted.

- Auth: `Authorization: Bearer <access_token>`
- Pagination: page-number with `page` and `page_size` (default 10, max 100)
- Dates: ISO 8601 (e.g., `2025-09-08T09:30:00Z`), dates as `YYYY-MM-DD`

## Projects

Base path: `/api/projects/`

### List Projects
- `GET /api/projects/`
- Filters (query):
  - `status`: planning|active|paused|review|complete|cancelled|archived
  - `priority`: low|medium|high|critical
  - `name`: case-insensitive contains
  - `search`: free text across name/description
- Response: paginated list of Project summaries

Example:
```
GET /api/projects/?status=active&priority=high&page=1&page_size=20
```

### Create Project
- `POST /api/projects/`
- Body:
```
{
  "name": "Website Redesign",
  "description": "Refresh brand and UX",
  "client_name": "Client Inc.",
  "status": "planning",
  "priority": "high",
  "start_date": "2025-09-01",
  "due_date": "2025-11-15",
  "estimated_hours": 200,
  "budget": "25000.00",
  "tags": ["marketing", "web"]
}
```

### Retrieve / Update / Delete
- `GET /api/projects/{id}/`
- `PATCH /api/projects/{id}/` (or `PUT`)
- `DELETE /api/projects/{id}/`

### Milestones
- `GET /api/projects/milestones/`
- `POST /api/projects/milestones/`
- `GET /api/projects/milestones/{id}/`
- `PATCH /api/projects/milestones/{id}/`
- `DELETE /api/projects/milestones/{id}/`

Milestone body (create/update):
```
{
  "project": 12,
  "name": "UX complete",
  "description": "Wireframes approved",
  "due_date": "2025-09-30",
  "completed": false,
  "reward": "Team dinner"
}
```

### Project Comments (nested)
- `GET /api/projects/{project_id}/comments/`
- `POST /api/projects/{project_id}/comments/` Body: `{ "content": "text", "is_internal": true }`

### Project Tasks (nested)
- `GET /api/projects/{project_id}/tasks/`
- Supports same filters as `/api/tasks/` (see below).

---

## Tasks

Base path: `/api/tasks/`

### List & Filter Tasks
- `GET /api/tasks/`
- Filters (query):
  - `project`: number (project ID)
  - `status`: todo|in_progress|done
  - `priority`: low|medium|high|critical
  - `due_date_after`, `due_date_before`: ISO datetime
  - `assigned_to`: user ID
  - `assigned_team`: department ID
  - `origin_app`: tasks|projects|digital|leads|finance|field
  - `tag`: tag label
  - `snoozed`: true|false
  - `overdue`: true
  - `search`: in title/description
  - `personal`: true (only personal tasks created/owned by user with no project)

Examples:
```
GET /api/tasks/?assigned_team=3&status=todo&priority=high
GET /api/tasks/?overdue=true
GET /api/tasks/?project=12&tag=urgent
GET /api/tasks/?personal=true
```

### Create Task
- `POST /api/tasks/`
- Body (fields are optional unless noted):
```
{
  "project": 12,                // optional for personal tasks
  "title": "Prepare invoice",
  "description": "Draft and send Q3 invoice",
  "priority": "medium",
  "due_date": "2025-09-12T16:00:00Z",
  "start_at": null,
  "earliest_start_at": null,
  "latest_finish_at": null,
  "snoozed_until": null,
  "backlog_date": null,         // YYYY-MM-DD
  "estimated_minutes": 90,
  "estimated_hours": null,
  "assigned_to": 7,
  "assigned_team": 3,
  "notes": "Attach PO",
  "origin_app": "projects",
  "milestone": 21,
  "dependencies": [101, 102],
  "tags": ["finance", "urgent"],
  "is_hard_due": false,
  "parent": null,
  "context_energy": "medium",  // low|medium|high
  "context_location": "office",
  "recurrence_rule": null       // e.g. RFC5545 RRULE
}
```

### Retrieve / Update / Delete
- `GET /api/tasks/{id}/`
- `PATCH /api/tasks/{id}/` (or `PUT`)
- `DELETE /api/tasks/{id}/`

### Quick Actions
- Toggle complete: `POST /api/tasks/{id}/toggle/`
- Mark complete: `POST /api/tasks/{id}/complete/`
- Snooze: `POST /api/tasks/{id}/snooze` Body: `{ "until": "2025-09-09T09:00:00Z" }`

### Team Tasks (by Department)
- `GET /api/tasks/teams/{team_id}/` (supports same filters as `/api/tasks/`)

### Task Response Shape (concise)
```
{
  "id": 101,
  "project": 12,
  "project_name": "Website Redesign",
  "title": "Prepare invoice",
  "description": "...",
  "status": "in_progress",
  "priority": "high",
  "due_date": "2025-09-12T16:00:00Z",
  "start_at": null,
  "earliest_start_at": null,
  "latest_finish_at": null,
  "snoozed_until": null,
  "backlog_date": null,
  "estimated_minutes": 90,
  "estimated_hours": null,
  "actual_hours": 0,
  "assigned_to": 7,
  "assigned_to_email": "user@example.com",
  "assigned_team": 3,
  "assigned_team_name": "Finance",
  "dependencies": [100],
  "milestone": 21,
  "origin_app": "projects",
  "created_by": 2,
  "notes": "Attach PO",
  "position": 0,
  "is_completed": false,
  "completed_at": null,
  "is_hard_due": false,
  "parent": null,
  "context_energy": "medium",
  "context_location": "office",
  "recurrence_rule": null,
  "created_at": "2025-09-05T10:00:00Z",
  "updated_at": "2025-09-05T10:00:00Z",
  "is_overdue": false
}
```

---

## Planner

Base path: `/api/planner/`

### Preview Schedule
- `POST /api/planner/schedule/preview`
- Body:
```
{ "scope": "day" | "week", "date": "YYYY-MM-DD" }
```
- Response:
```
{
  "blocks": [
    { "task_id": 101, "title": "Prepare invoice", "start": "2025-09-08T09:00:00+00:00", "end": "2025-09-08T09:25:00+00:00", "is_break": false },
    { "task_id": null, "title": "Break", "start": "2025-09-08T09:25:00+00:00", "end": "2025-09-08T09:30:00+00:00", "is_break": true }
  ],
  "capacity_usage": 0.65,
  "window_minutes": 420,
  "planned_minutes": 270
}
```

Notes:
- Availability uses per-user templates (fallback 09:00–17:00), minus busy `CalendarEvent`s.
- Pomodoro policy (focus/break) comes from `BreakPolicy` (user/team), else defaults 25/5/15.

### Commit Schedule
- `POST /api/planner/schedule/commit`
- Body: same as preview (recomputes and persists `TimeBlock`s with `status=committed`).
- Response: persisted `TimeBlock[]` records.

### Replan
- `POST /api/planner/replan` — same input/output as preview (non-destructive).

### Time Blocks
- `GET /api/planner/blocks?start=ISO&end=ISO`
- `GET /api/planner/blocks/{id}/`
- `PATCH /api/planner/blocks/{id}/`
  - Body: e.g. `{ "status": "in_progress" }` or drag/resize `{ "start": "...", "end": "..." }`
- `DELETE /api/planner/blocks/{id}/`

`TimeBlock` fields (important): `title`, `task`, `start`, `end`, `status` (planned|committed|in_progress|done|skipped), `is_break`.

### Calendar Events (availability/busy)
- `GET /api/planner/events`
- `POST /api/planner/events` Body:
```
{ "title": "Standup", "description": "Daily", "start": "ISO", "end": "ISO", "is_busy": true }
```
- `GET /api/planner/events/{id}/`
- `PATCH /api/planner/events/{id}/`
- `DELETE /api/planner/events/{id}/`

---

## Teams and Departments
- Departments live under `/api/accounts/departments/`.
- Use the department `id` for `assigned_team` on tasks and for filtering `/api/tasks/?assigned_team=...`.

---

## Status Codes
- 200 OK – Success (GET/PATCH)
- 201 Created – Resource created (POST)
- 204 No Content – Deleted
- 400 Bad Request – Validation/error parsing input
- 401 Unauthorized – Missing/invalid token
- 403 Forbidden – Not allowed
- 404 Not Found – Missing resource

---

## Pagination
- Enabled on list endpoints by default.
- Query params: `page`, `page_size` (default 10, max 100).
- Response includes standard DRF pagination keys when configured (e.g., `count`, `next`, `previous`, `results`).

---

## Notes & Conventions
- Trailing slashes are used throughout (e.g., `/tasks/`, `/tasks/1/`).
- All datetimes are timezone-aware.
- Filter parameters are case-insensitive where appropriate.
- Planner configuration entities (`BreakPolicy`, `AvailabilityTemplate`) are managed via admin in this phase.

