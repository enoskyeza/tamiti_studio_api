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

**Note:** Comments now support threading and @mentions. See Comments section below for full API.

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
  - `status`: todo|in_progress|done|review
  - `priority`: low|medium|high|urgent
  - `due_date_after`, `due_date_before`: ISO datetime
  - `assigned_to`: user ID (supports multiple users)
  - `assigned_team`: department ID (supports multiple teams)
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
  "priority": "medium",         // low|medium|high|urgent
  "status": "todo",             // todo|in_progress|done|review
  "due_date": "2025-09-12T16:00:00Z",
  "start_at": null,
  "earliest_start_at": null,
  "latest_finish_at": null,
  "snoozed_until": null,
  "backlog_date": null,         // YYYY-MM-DD
  "estimated_minutes": 90,
  "estimated_hours": null,
  "assigned_users": [7, 8],     // multiple users supported
  "assigned_teams": [3, 4],     // multiple teams supported
  "notes": "Attach PO",
  "origin_app": "projects",
  "milestone": 21,
  "dependencies": [101, 102],
  "tags": ["finance", "urgent"],
  "is_hard_due": false,
  "parent": null,
  "context_energy": "medium",  // low|medium|high
  "context_location": "office",
  "recurrence_rule": null,      // e.g. RFC5545 RRULE
  "kanban_column": null,        // for Kanban board assignment
  "kanban_position": null       // position within column
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
  "projectId": 12,              // mockup compatibility
  "title": "Prepare invoice",
  "description": "...",
  "status": "in_progress",
  "priority": "high",
  "due_date": "2025-09-12T16:00:00Z",
  "dueDate": "2025-09-12T16:00:00Z",  // mockup compatibility
  "start_at": null,
  "earliest_start_at": null,
  "latest_finish_at": null,
  "snoozed_until": null,
  "backlog_date": null,
  "estimated_minutes": 90,
  "estimated_hours": null,
  "estimatedHours": null,       // mockup compatibility
  "actual_hours": 0,
  "actualHours": 0,             // mockup compatibility
  "assigned_users": [7, 8],     // multiple users
  "assignedUsers": [            // mockup compatibility
    {"id": 7, "username": "john", "full_name": "John Doe"},
    {"id": 8, "username": "jane", "full_name": "Jane Smith"}
  ],
  "assigned_teams": [3, 4],     // multiple teams
  "assignedTeams": [            // mockup compatibility
    {"id": 3, "name": "Finance"},
    {"id": 4, "name": "Marketing"}
  ],
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
  "kanban_column": 5,
  "kanban_position": 2,
  "created_at": "2025-09-05T10:00:00Z",
  "createdAt": "2025-09-05T10:00:00Z",  // mockup compatibility
  "updated_at": "2025-09-05T10:00:00Z",
  "updatedAt": "2025-09-05T10:00:00Z",  // mockup compatibility
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

## Kanban Boards

Base path: `/api/tasks/kanban/`

### List/Create Kanban Boards
- `GET /api/tasks/kanban/boards/` - List all boards
- `POST /api/tasks/kanban/boards/` - Create new board

Create board body:
```
{
  "name": "Sprint 1 Board",
  "description": "Main development board",
  "project": 12
}
```

### Board Details
- `GET /api/tasks/kanban/boards/{id}/` - Get board with columns and tasks
- `PATCH /api/tasks/kanban/boards/{id}/` - Update board
- `DELETE /api/tasks/kanban/boards/{id}/` - Delete board

### Initialize Board with Default Columns
- `POST /api/tasks/kanban/boards/{id}/initialize/`
- Creates default columns based on task statuses

### Kanban Columns
- `GET /api/tasks/kanban/columns/` - List columns
- `POST /api/tasks/kanban/columns/` - Create column
- `GET /api/tasks/kanban/columns/{id}/` - Get column details
- `PATCH /api/tasks/kanban/columns/{id}/` - Update column
- `DELETE /api/tasks/kanban/columns/{id}/` - Delete column

Create column body:
```
{
  "name": "In Review",
  "board": 5,
  "status_mapping": "review",
  "order": 3,
  "color": "#FFA500",
  "wip_limit": 5
}
```

### Task Movement
- `POST /api/tasks/kanban/move-task/` - Move task between columns
- `POST /api/tasks/kanban/reorder-task/` - Reorder task within column

Move task body:
```
{
  "task_id": 101,
  "target_column_id": 6,
  "position": 2
}
```

Reorder task body:
```
{
  "task_id": 101,
  "new_position": 1
}
```

---

## Comments System

Base path: `/api/comments/`

### List/Create Comments
- `GET /api/comments/?target_type=tasks.task&target_id=123` - List comments for object
- `POST /api/comments/` - Create new comment

Create comment body:
```
{
  "content": "Great work @john.doe! Please review this task.",
  "target_type": "tasks.task",  // app_label.model
  "target_id": 123,
  "is_internal": false
}
```

### Comment Details
- `GET /api/comments/{id}/` - Get comment details
- `PATCH /api/comments/{id}/` - Update comment (author only)
- `DELETE /api/comments/{id}/` - Soft delete comment (author only)

### Comment Replies (1-level deep)
- `POST /api/comments/{comment_id}/replies/` - Reply to comment
- `GET /api/comments/{comment_id}/replies/list/` - Get all replies

Reply body:
```
{
  "content": "Thanks for the feedback @jane.smith!"
}
```

### Comment Actions
- `POST /api/comments/{id}/toggle-internal/` - Toggle internal status

### User Mentions
- `GET /api/comments/search-users/?query=john` - Search users for @mentions

Response:
```
[
  {
    "id": 7,
    "username": "john.doe",
    "email": "john@example.com",
    "full_name": "John Doe",
    "avatar": null
  }
]
```

### Comment Response Shape
```
{
  "id": 45,
  "content": "Great work @john.doe!",
  "author": {
    "id": 2,
    "username": "jane.smith",
    "full_name": "Jane Smith"
  },
  "target_type": "tasks.task",
  "target_id": 123,
  "parent": null,              // null for top-level comments
  "replies": [                 // nested replies
    {
      "id": 46,
      "content": "Thanks!",
      "author": {...},
      "parent": 45,
      "created_at": "2025-09-08T14:30:00Z"
    }
  ],
  "mentioned_users": [         // users mentioned in content
    {
      "id": 7,
      "username": "john.doe",
      "full_name": "John Doe"
    }
  ],
  "is_internal": false,
  "is_edited": false,
  "edited_at": null,
  "created_at": "2025-09-08T14:25:00Z",
  "updated_at": "2025-09-08T14:25:00Z"
}
```

---

## Permissions System

Base path: `/api/permissions/`

### Permissions Management
- `GET /api/permissions/permissions/` - List permissions
- `POST /api/permissions/permissions/` - Create permission
- `GET /api/permissions/permissions/{id}/` - Get permission details
- `PATCH /api/permissions/permissions/{id}/` - Update permission
- `DELETE /api/permissions/permissions/{id}/` - Delete permission

Filters:
- `content_type`: app_label.model
- `action`: create|read|update|delete|list
- `permission_type`: allow|deny
- `is_active`: true|false

Create permission body:
```
{
  "name": "Task Update Permission",
  "description": "Allow users to update tasks",
  "action": "update",
  "permission_type": "allow",
  "scope": "global",           // global|object|field
  "content_type_str": "tasks.task",
  "users": [7, 8],
  "groups": [2],
  "priority": 10,
  "is_active": true
}
```

### Permission Groups
- `GET /api/permissions/permission-groups/` - List permission groups
- `POST /api/permissions/permission-groups/` - Create group
- `GET /api/permissions/permission-groups/{id}/` - Get group details
- `PATCH /api/permissions/permission-groups/{id}/` - Update group
- `DELETE /api/permissions/permission-groups/{id}/` - Delete group

### Permission Checking
- `POST /api/permissions/check-permission/` - Check user permission

Check permission body:
```
{
  "action": "update",
  "content_type": "tasks.task",
  "object_id": 123,           // optional for object-specific
  "field_name": "status"      // optional for field-specific
}
```

### User Permissions
- `GET /api/permissions/user-permissions/?user_id=7` - Get user's permissions
- `GET /api/permissions/content-type-permissions/` - Permission overview by model
- `GET /api/permissions/stats/` - Permission system statistics

### Permission Logs (Audit)
- `GET /api/permissions/permission-logs/` - View permission check logs

Filters:
- `user_id`: filter by user
- `content_type`: filter by model
- `permission_granted`: true|false

### Cache Management
- `POST /api/permissions/clear-cache/` - Clear permission cache

Body (optional):
```
{
  "user_id": 7  // clear cache for specific user, omit for all users
}
```

### Bulk Operations
- `POST /api/permissions/permissions/bulk_assign/` - Bulk assign/remove permissions

Bulk assign body:
```
{
  "permission_ids": [1, 2, 3],
  "user_ids": [7, 8],
  "group_ids": [2],
  "action": "assign"           // assign|remove
}
```

---

---

## Enhanced Planner Features

### Smart Scheduling

#### Enhanced Schedule Preview
- `POST /api/planner/schedule/preview/` - Generate optimized schedule with AI-like algorithms

Request body:
```json
{
  "scope": "day",        // day|week
  "date": "2024-01-15",
  "smart": true           // Use enhanced algorithms (default: true)
}
```

Response:
```json
{
  "blocks": [
    {
      "task_id": 42,
      "title": "Review project proposal",
      "start": "2024-01-15T09:00:00Z",
      "end": "2024-01-15T10:30:00Z",
      "is_break": false
    },
    {
      "task_id": null,
      "title": "Break",
      "start": "2024-01-15T10:30:00Z",
      "end": "2024-01-15T10:45:00Z",
      "is_break": true
    }
  ],
  "capacity_usage": 0.85,
  "window_minutes": 480,
  "planned_minutes": 408
}
```

#### Smart Replanning
- `POST /api/planner/replan/` - Intelligently reschedule incomplete tasks

Request body:
```json
{
  "from_date": "2024-01-15",
  "to_date": "2024-01-22"     // Optional, defaults to next week
}
```

Response:
```json
{
  "rescheduled_count": 5,
  "tasks": [
    {"id": 42, "title": "Review project proposal"},
    {"id": 43, "title": "Update documentation"}
  ],
  "new_schedule": {
    "blocks": [...],
    "capacity_usage": 0.75
  }
}
```

#### Bulk Task Rescheduling
- `POST /api/planner/bulk-reschedule/` - Reschedule multiple tasks at once

Request body:
```json
{
  "task_ids": [42, 43, 44],
  "target_date": "2024-01-22"
}
```

### Daily Productivity Tracking

#### Daily Reviews
- `GET /api/planner/daily-reviews/` - List daily reviews
- `POST /api/planner/daily-reviews/` - Create daily review
- `GET /api/planner/daily-reviews/{id}/` - Get specific review
- `PATCH /api/planner/daily-reviews/{id}/` - Update review

Daily review structure:
```json
{
  "id": 1,
  "date": "2024-01-15",
  "summary": "Productive day with good focus",
  "mood": "good",           // excellent|good|neutral|poor|terrible
  "highlights": "Completed major feature implementation",
  "lessons": "Need to take more breaks for better focus",
  "tomorrow_top3": [
    "Review pull requests",
    "Client meeting prep",
    "Update project timeline"
  ],
  
  // Auto-calculated metrics
  "tasks_planned": 8,
  "tasks_completed": 6,
  "completion_rate": 75.00,
  "focus_time_minutes": 420,
  "break_time_minutes": 60,
  "productivity_score": 82.50,
  "current_streak": 5,
  
  "created_at": "2024-01-15T18:00:00Z",
  "updated_at": "2024-01-15T18:00:00Z"
}
```

#### Compute Daily Metrics
- `POST /api/planner/daily-reviews/compute_metrics/` - Calculate metrics for specific date

Request body:
```json
{
  "date": "2024-01-15"
}
```

#### Productivity Statistics
- `GET /api/planner/daily-reviews/productivity_stats/?days=30` - Get productivity trends

Response:
```json
{
  "avg_productivity_score": 78.50,
  "avg_completion_rate": 72.30,
  "current_streak": 5,
  "total_focus_hours": 156.5,
  "trend": "improving",      // improving|stable|declining|no_data
  "total_days": 30
}
```

### Work Goals Management

#### Work Goals (Separate from Finance Goals)
- `GET /api/planner/work-goals/` - List work goals
- `POST /api/planner/work-goals/` - Create work goal
- `GET /api/planner/work-goals/{id}/` - Get specific goal
- `PATCH /api/planner/work-goals/{id}/` - Update goal
- `DELETE /api/planner/work-goals/{id}/` - Delete goal

Work goal structure:
```json
{
  "id": 1,
  "name": "Complete Q1 Feature Development",
  "description": "Deliver all planned features for Q1 release",
  "target_date": "2024-03-31",
  "owner_user": 7,
  "owner_team": null,
  "project": 5,
  "tags": ["q1", "features", "development"],
  "is_active": true,
  
  // Auto-calculated progress
  "progress_percentage": 65.50,
  "total_tasks": 20,
  "completed_tasks": 13,
  
  // Computed fields
  "owner_user_email": "john@example.com",
  "owner_team_name": null,
  "project_name": "Mobile App Redesign",
  
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-15T12:00:00Z"
}
```

#### Update Goal Progress
- `POST /api/planner/work-goals/{id}/update_progress/` - Manually recalculate progress

Query parameters:
- `active_only=true` - Filter active goals only (default: true)

### Productivity Insights

#### View Insights
- `GET /api/planner/insights/` - List productivity insights
- `GET /api/planner/insights/{id}/` - Get specific insight

Insight structure:
```json
{
  "id": 1,
  "insight_type": "peak_hours",
  "data": {
    "hours": [9, 10, 11, 14, 15]
  },
  "confidence_score": 85.50,
  "sample_size": 42,
  "valid_from": "2024-01-15",
  "valid_until": null,
  "is_active": true,
  "created_at": "2024-01-15T12:00:00Z",
  "updated_at": "2024-01-15T12:00:00Z"
}
```

Insight types:
- `peak_hours` - Most productive hours of the day
- `task_duration` - Optimal task duration in minutes
- `break_pattern` - Optimal break-to-work ratio
- `weekly_trend` - Productivity by day of week
- `completion_pattern` - Task completion patterns

#### Generate Fresh Insights
- `POST /api/planner/insights/generate_insights/` - Compute new insights from recent data

Response:
```json
{
  "generated_count": 4,
  "insights": {
    "peak_hours": {...},
    "task_duration": {...},
    "break_pattern": {...},
    "weekly_trend": {...}
  }
}
```

### Productivity Dashboard

#### Comprehensive Dashboard
- `GET /api/planner/dashboard/` - Get complete productivity overview

Response:
```json
{
  "latest_review": {
    "date": "2024-01-15",
    "productivity_score": 82.50,
    "completion_rate": 75.00,
    "current_streak": 5
  },
  "active_goals": [
    {
      "id": 1,
      "name": "Complete Q1 Features",
      "progress_percentage": 65.50,
      "target_date": "2024-03-31"
    }
  ],
  "insights": [
    {
      "insight_type": "peak_hours",
      "data": {"hours": [9, 10, 11, 14, 15]},
      "confidence_score": 85.50
    }
  ],
  "upcoming_tasks": [
    {
      "id": 1,
      "title": "Review pull requests",
      "start": "2024-01-16T09:00:00Z",
      "end": "2024-01-16T10:00:00Z",
      "task_title": "Review pull requests",
      "task_priority": "high"
    }
  ],
  "dashboard_generated_at": "2024-01-15T18:00:00Z"
}
```

### Enhanced Time Blocks

Time blocks now include additional computed fields:
```json
{
  "id": 1,
  "owner_user": 7,
  "task": 42,
  "title": "Review project proposal",
  "start": "2024-01-15T09:00:00Z",
  "end": "2024-01-15T10:30:00Z",
  "status": "planned",
  "is_break": false,
  "source": "auto",
  
  // Computed fields
  "duration_minutes": 90,
  "task_title": "Review project proposal",
  "task_priority": "high",
  
  "created_at": "2024-01-15T08:00:00Z",
  "updated_at": "2024-01-15T08:00:00Z"
}
```

---

## Performance Features

### Caching
- Schedule previews are cached for 5 minutes
- Productivity insights are cached until new data is available
- User patterns are cached for optimal performance

### Background Processing
- Daily metrics computation via management command:
  ```bash
  python manage.py compute_daily_metrics --date=2024-01-15
  python manage.py compute_daily_metrics --generate-insights
  ```

### Bulk Operations
- Bulk task rescheduling (up to 50 tasks)
- Bulk permission assignments
- Efficient database queries with proper indexing

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
- Smart scheduling algorithms provide AI-like intelligence without requiring ML models.
- Productivity metrics are calculated using research-based algorithms.
- All endpoints support proper error handling and validation.
- Planner configuration entities (`BreakPolicy`, `AvailabilityTemplate`) are managed via admin in this phase.

