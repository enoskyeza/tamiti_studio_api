# RFC: Tasks, Projects, and Planner Foundations

- Status: Draft
- Owner: Tamiti Studio Team
- Created: 2025-09-04
- Scope: Tasks, Projects, Planner foundations (no auth concerns)

## Summary

This RFC proposes a cohesive structure to evolve the Tasks and Projects apps so tasks are flexible (project-bound or independent), team-aware, and planner-ready. It also introduces a clear separation between Finance goals and Work goals (project/task-related), and defines minimal planner-facing contracts required for day planning, time-blocking, snoozing, and simple rescheduling.

Non-goals: authentication, tokens, trailing slashes, or unrelated API conventions.

## Motivation

- Use tasks as a universal primitive across the platform: project tasks, personal tasks, team checklists (e.g., weekly Finance tasks), and ad-hoc reminders.
- Enable a day/week planner to schedule tasks into time blocks (with breaks) and to adjust plans when reality changes.
- Support journaling/daily reviews and long-term backlog dates without conflating with Finance goals.
- Align backend data models and endpoints to the planner UI expectations (tasks list, complete, snooze; basic schedule hooks), while keeping Projects unchanged where possible.

## Goals

- Flexible tasks usable with or without a project.
- Robust assignment to either a user or a team (department), leveraging Staff Profiles and Departments.
- Separation of Finance goals from Work goals (project/task goals).
- Basic planner interfaces for preview/commit/replan of schedules, without prescribing auth or URL trailing slash behavior here.
- Improved filtering and metadata to empower boards, calendars, and analytics.

## Non-Goals

- Do not alter auth, sessions, or token refresh behavior.
- Do not standardize trailing slashes; planner endpoints will be added as needed and can later be normalized platform-wide.
- Do not implement external calendar sync or AI-based planning in this phase.

## Current State (as of repo)

- Tasks exist and can be independent (`project` is nullable). Serializers and filters are present.
- Issues:
  - `Task.__str__` dereferences `project.name` (breaks when `project` is null).
  - `Task.save()` unconditionally updates the project’s completion percentage (breaks when `project` is null).
  - No native `start_at`, `snoozed_until`, or recurrence/template support.
  - No day-planner entities (time blocks, availability, or events) in backend.
  - Limited filtering (status/priority/due only), missing user/team, tags, snoozed, overdue, search.
- Projects work and compute completion via task counts.
- Finance goals exist under `/finance/goals/` and are currently distinct in code; the planner needs separate Work goals to avoid domain coupling.

## Proposal Overview

1) Harden and extend Tasks to serve as a universal, planner-ready unit.
2) Keep Projects app as-is with small robustness improvements and optional computed views.
3) Introduce Work goals distinct from Finance goals.
4) Add minimal planner-facing entities and endpoints limited to task scheduling needs.
5) Model team ownership via Departments/Staff Profiles.

## Data Model Changes

### Task (extend existing)

Add fields for planning, flexibility, and team ownership:

- `start_at: datetime | null` — preferred start time for the task.
- `earliest_start_at: datetime | null` — do not schedule before this.
- `latest_finish_at: datetime | null` — soft deadline for scheduling.
- `snoozed_until: datetime | null` — don’t show/schedule until this.
- `estimated_minutes: int | null` — finer-grained estimates; keep `estimated_hours` for backward compatibility (UI can prefer minutes).
- `effort_points: int | null` — optional backlog/relative sizing.
- `is_hard_due: bool` — indicates due date is hard; planner must respect.
- `parent: FK(Task) | null` — allows subtasks.
- `context_energy: enum(low|medium|high) | null` — planner hint.
- `context_location: string | null` — planner hint (e.g., office/home/field).
- `backlog_date: date | null` — “not before” date for future tasks (e.g., six months out).
- `recurrence_rule: text | null` — RFC5545 RRULE or simple custom string; used by a template engine to generate instances.
- `assigned_team: FK(Department) | null` — team-level assignment (alongside `assigned_to` for individual ownership).

Behavioral fixes:

- Make `__str__` and `save()` null-safe for `project`.
- On toggle complete, set `status='done'` and `completed_at` accordingly; on reopen, clear `completed_at`.

Indexes (implementation detail): add indexes on `status`, `is_completed`, `due_date`, `snoozed_until`, `assigned_to`, `assigned_team`.

### Project (minor)

- No structural change required. Optionally:
  - `type: enum(client|internal|ops|personal)` for grouping.
  - Computed properties for task counts already exist; keep as-is.

### Work Goals (new, separate from Finance)

Introduce a small model for “Work goals” (project/task oriented):

- `name: string`
- `description: text`
- `target_date: date | null`
- `owner_user: FK(User) | null`
- `owner_team: FK(Department) | null`
- `project: FK(Project) | null`
- `progress: computed` (e.g., via linked tasks or milestones)
- `tags: string[]` (optional)

Rationale: keep `/finance/goals/` financial, and add `/goals/` for work/productivity goals.

### Planner Entities (minimal set for task scheduling)

Keep the scope tight; enough to make day/week scheduling possible:

- TimeBlock: `task (FK|null)`, `kind('task'|'break'|'buffer')`, `date`, `starts_at`, `ends_at`, `duration_minutes`, `status('planned'|'active'|'done'|'canceled')`, `owner_user`, `owner_team`, `notes`.
- CalendarEvent: `title`, `starts_at`, `ends_at`, `busy: bool`, `type`, `owner_user`, `owner_team`.
- AvailabilityTemplate: per-user/team day-of-week availability windows (`weekday`, `start_time`, `end_time`, `is_workday`).
- BreakPolicy: `focus_minutes`, `short_break_minutes`, `long_break_minutes`, `long_every`, `max_daily_focus_minutes`.
- DailyReview: `date`, `summary`, `mood`, `highlights`, `lessons`, `tomorrow_top3`, `owner_user`.

Note: Planner entities are included here because they are necessary to fulfill the “auto-plan and reschedule” needs of tasks, but this RFC does not address authentication or global API conventions.

## Endpoints (Tasks/Projects/Planner-focused)

### Tasks

- `GET /tasks` — filters: `status`, `priority`, `project`, `assigned_to`, `assigned_team`, `origin_app`, `tags`, `due_date` (range), `overdue(bool)`, `snoozed(bool)`, `search`, pagination.
- `POST /tasks` — create (accept new fields; keep compatibility with existing payloads).
- `GET /tasks/:id` — retrieve.
- `PATCH /tasks/:id` — partial update.
- `DELETE /tasks/:id` — optional (archival via status also supported).
- `POST /tasks/:id/complete` — mark complete; returns updated task.
- `POST /tasks/:id/snooze` — `{ until: ISO8601 }`; updates `snoozed_until`.

### Projects

- Keep current CRUD for `/projects/` and `/projects/:id/`.
- Optional convenience: `GET /projects/:id/tasks` — list tasks for a project with same filters as `/tasks` (server can implement via filter param `?project=:id`).

### Work Goals (separate from Finance)

- `GET /goals` — list work goals.
- `POST /goals` — create work goal.
- `GET /goals/:id` — retrieve.
- `PATCH /goals/:id` — update.
- `DELETE /goals/:id` — delete.

### Planner Interfaces (minimal)

- `POST /schedule/preview` — `{ scope: 'day'|'week', date }` → `{ blocks, conflicts, capacity_usage }` (non-persistent preview).
- `POST /schedule/commit` — `{ block_ids: number[] }` → persists selected blocks as TimeBlocks.
- `POST /replan` — re-generate preview given current facts; planner may invalidate planned-but-not-started blocks.
- `GET /blocks` — query current/past/future blocks by date/scope.
- `PATCH /blocks/:id` — drag/resize/status updates.
- `CRUD /events` — user-entered calendar events for availability/conflicts.

## Team and Ownership Model

- Users are represented via Staff Profiles; teams are Departments. We will:
  - Add `assigned_team: FK(Department) | null` on Task to support team tasks.
  - Keep `assigned_to: FK(User) | null` for individual ownership.
  - TimeBlocks, Goals, and Events also carry `owner_user` and/or `owner_team` to cleanly support personal vs team planning.
- Filters should support both `assigned_to` and `assigned_team` for boards and reports.

## Planner Algorithm (V1 overview)

- Input: candidate tasks not completed, not snoozed past date, dependencies resolved, within time windows. Availability derived from templates minus calendar busy events.
- Scoring: combine `priority`, due proximity, overdue boost, fit-to-slot (small tasks fill gaps), and optional context hints.
- Expansion: split tasks into `focus_minutes` chunks and insert breaks per BreakPolicy.
- Packing: greedy earliest-fit into free capacity across day/week; produce conflicts when capacity is insufficient.
- Preview vs Commit: preview never persists; commit writes `TimeBlock` records.

## API Contracts (concise)

### Task (GET shape)

```
{
  id: number,
  title: string,
  description?: string,
  status: 'todo'|'in_progress'|'done',
  priority: 'low'|'medium'|'high'|'critical',
  is_completed: boolean,
  project?: { id: number, name: string } | number | null,
  assigned_to?: { id: number, email: string } | number | null,
  assigned_team?: { id: number, name: string } | number | null,
  due_date?: ISODateTime,
  start_at?: ISODateTime,
  earliest_start_at?: ISODateTime,
  latest_finish_at?: ISODateTime,
  snoozed_until?: ISODateTime,
  estimated_minutes?: number,
  estimated_hours?: number | null,
  tags?: string[],
  created_at: ISODateTime,
  updated_at: ISODateTime
}
```

### Complete

```
POST /tasks/:id/complete
-> returns Task (status='done', is_completed=true, completed_at set)
```

### Snooze

```
POST /tasks/:id/snooze
Body: { until: ISODateTime }
-> returns Task (snoozed_until updated)
```

### Work Goal

```
{
  id: number,
  name: string,
  description?: string,
  target_date?: ISODate,
  owner_user?: number,
  owner_team?: number,
  project?: number,
  progress?: number,
  tags?: string[],
  created_at: ISODateTime,
  updated_at: ISODateTime
}
```

## Migration & Compatibility Plan

- Add new nullable fields to `Task`; maintain existing serializers to avoid breaking writes. Prefer adding new serializers fields as optional.
- Extend `TaskFilter` with `assigned_to`, `assigned_team`, `tags`, `snoozed(bool)`, `overdue(bool)`, and `search`.
- Add `POST /tasks/:id/complete` and `POST /tasks/:id/snooze` endpoints.
- Guard `Task.__str__` and `save()` when `project` is null.
- Introduce Work Goal model and endpoints; leave Finance goals untouched.
- Introduce minimal planner endpoints/entities in a new app (e.g., `planner`) without impacting existing modules.

## Delivery Phases

1. Foundation
   - Add task fields and null-safety fixes.
   - Extend filters; add complete/snooze endpoints.
2. Planner Core (minimal)
   - Add `planner` app: TimeBlock, CalendarEvent, AvailabilityTemplate, BreakPolicy.
   - Implement `/schedule/preview`, `/schedule/commit`, `/replan`, `/blocks`, `/events`.
3. Goals & Reviews
   - Add Work Goals (`/goals`) separate from Finance; optional DailyReview.
4. Templates & Teams
   - Task templates/recurrence; weekly team tasks (Departments) and personal recurring tasks.
5. Hardening
   - Indexes, background jobs (nightly re-plans), OpenAPI updates, tests.

## Open Questions

- Where to locate Work Goals: separate `planner` app or within `projects`? Recommendation: `planner` to avoid coupling, but allow optional link to `project`.
- Task assignment precedence: if both `assigned_team` and `assigned_to` exist, should filtering default to user or team? Suggest both, with UI controls.
- Recurrence engine: support iCal RRULE vs a simpler rule set initially?

## Risks

- Increased model complexity for Task; mitigation: keep new fields optional and add indexes.
- Planner algorithm expectations vs. reality; mitigation: start with a clear V1 and iterate.
- Team ownership edge cases (cross-department tasks); mitigation: allow both user and team and filter accordingly.

## Out of Scope (for this RFC)

- Auth changes, SSO, or token refresh logic.
- External calendar integrations and two-way sync.
- AI-based planning or learning from journals (future work).

