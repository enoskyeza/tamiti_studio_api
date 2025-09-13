# Tasks App - Complete API Documentation

## Overview

The Tasks app is a comprehensive task and project management system that provides task creation, assignment, tracking, and collaboration features. It supports Kanban boards, backlog management, task checklists, team assignments, and advanced scheduling capabilities. The app integrates with the projects system and supports both personal and team-based workflows.

## Core Models and Data Structures

### 1. Task Model
**Purpose**: Core model representing individual tasks with comprehensive planning and tracking capabilities

**Fields**:
- `id` (AutoField, primary key) - Unique task identifier
- `project` (ForeignKey to Project, nullable) - Associated project (null for personal tasks)
- `title` (CharField, max_length=200) - Task title
- `description` (TextField, blank=True) - Detailed task description
- `status` (CharField, choices=TaskStatus.choices, default=TODO) - Current task status
- `priority` (CharField, choices=PriorityLevel.choices, default=MEDIUM) - Task priority level
- `due_date` (DateTimeField, nullable) - Task deadline
- `start_at` (DateTimeField, nullable) - Planned start time
- `earliest_start_at` (DateTimeField, nullable) - Earliest possible start time
- `latest_finish_at` (DateTimeField, nullable) - Latest acceptable finish time
- `snoozed_until` (DateTimeField, nullable) - Snooze until specific datetime
- `backlog_date` (DateField, nullable) - Date when task was added to backlog
- `estimated_minutes` (PositiveIntegerField, nullable) - Estimated duration in minutes
- `estimated_hours` (PositiveIntegerField, nullable) - Estimated duration in hours
- `actual_hours` (PositiveIntegerField, default=0) - Actual time spent
- `assigned_to` (ForeignKey to User, nullable) - Primary assignee
- `assigned_users` (ManyToManyField to User) - Multiple assignees
- `assigned_team` (ForeignKey to Department, nullable) - Primary assigned team
- `assigned_teams` (ManyToManyField to Department) - Multiple assigned teams
- `dependencies` (ManyToManyField to self) - Task dependencies
- `milestone` (ForeignKey to Milestone, nullable) - Associated milestone
- `origin_app` (CharField, choices=OriginApp.choices) - App that created the task
- `created_by` (ForeignKey to User) - Task creator
- `tags` (TaggableManager) - Task tags for categorization
- `notes` (TextField, blank=True) - Additional notes
- `position` (PositiveIntegerField, default=0) - General ordering position
- `kanban_column` (ForeignKey to KanbanColumn, nullable) - Current Kanban column
- `kanban_position` (PositiveIntegerField, default=0) - Position within Kanban column
- `is_completed` (BooleanField, default=False) - Completion status
- `completed_at` (DateTimeField, nullable) - Completion timestamp
- `is_hard_due` (BooleanField, default=False) - Whether due date is strict
- `parent` (ForeignKey to self, nullable) - Parent task for subtasks
- `context_energy` (CharField, choices=EnergyLevel.choices, nullable) - Required energy level
- `context_location` (CharField, max_length=100, nullable) - Required location context
- `recurrence_rule` (TextField, nullable) - Recurrence pattern definition
- `created_at` (DateTimeField, auto_now_add=True)
- `updated_at` (DateTimeField, auto_now=True)

**Properties**:
- `is_overdue` - Returns True if task is past due date and not completed
- `projectId` - Alias for project_id (API compatibility)
- `assignedUsers` - Combined list of assigned user IDs
- `assignedTeams` - Combined list of assigned team IDs
- `dueDate` - ISO formatted due date string
- `estimatedHours` - Alias for estimated_hours
- `actualHours` - Alias for actual_hours
- `createdAt` - ISO formatted creation date
- `updatedAt` - ISO formatted update date

**Methods**:
- `move_to_column(target_column, position=None)` - Move task to different Kanban column
- `reorder_in_column(new_position)` - Reorder task within same column
- `save()` - Override to handle completion status and project updates

### 2. BacklogItem Model
**Purpose**: Simple backlog for capturing ideas and tasks without detailed planning

**Fields**:
- `id` (AutoField, primary key) - Unique identifier
- `title` (CharField, max_length=255) - Backlog item title
- `source` (CharField, choices=Source.choices, default=PERSONAL) - Source type (personal/work/client)
- `created_by` (ForeignKey to User) - Item creator
- `converted_to_task` (ForeignKey to Task, nullable) - Converted task reference
- `is_converted` (BooleanField, default=False) - Conversion status
- `created_at` (DateTimeField, auto_now_add=True)
- `updated_at` (DateTimeField, auto_now=True)

**Methods**:
- `convert_to_task(**task_data)` - Convert backlog item to full task

### 3. TaskChecklist Model
**Purpose**: Checklist items for tasks to break down work into smaller actionable items

**Fields**:
- `id` (AutoField, primary key) - Unique identifier
- `task` (ForeignKey to Task) - Associated task
- `title` (CharField, max_length=255) - Checklist item title
- `is_completed` (BooleanField, default=False) - Completion status
- `completed_at` (DateTimeField, nullable) - Completion timestamp
- `position` (PositiveIntegerField, default=0) - Ordering position
- `created_at` (DateTimeField, auto_now_add=True)
- `updated_at` (DateTimeField, auto_now=True)

**Methods**:
- `mark_completed()` - Mark checklist item as completed
- `mark_incomplete()` - Mark checklist item as incomplete

### 4. KanbanBoard Model
**Purpose**: Represents a Kanban board for a project

**Fields**:
- `id` (AutoField, primary key) - Unique identifier
- `project` (OneToOneField to Project) - Associated project
- `name` (CharField, max_length=200, default="Project Board") - Board name
- `created_at` (DateTimeField, auto_now_add=True)
- `updated_at` (DateTimeField, auto_now=True)

### 5. KanbanColumn Model
**Purpose**: Represents a column in a Kanban board

**Fields**:
- `id` (AutoField, primary key) - Unique identifier
- `board` (ForeignKey to KanbanBoard) - Associated board
- `name` (CharField, max_length=100) - Column name
- `status_mapping` (CharField, choices=TaskStatus.choices, nullable) - Mapped task status
- `order` (PositiveIntegerField, default=0) - Column ordering
- `color` (CharField, max_length=7, default="#6B7280") - Column color (hex)
- `wip_limit` (PositiveIntegerField, nullable) - Work In Progress limit
- `created_at` (DateTimeField, auto_now_add=True)
- `updated_at` (DateTimeField, auto_now=True)

**Properties**:
- `task_count` - Number of tasks in column
- `is_wip_exceeded` - Whether WIP limit is exceeded

### 6. TaskGroup Model (Legacy)
**Purpose**: Legacy model for backward compatibility

**Fields**:
- `id` (AutoField, primary key) - Unique identifier
- `project` (ForeignKey to Project) - Associated project
- `name` (CharField, max_length=100) - Group name
- `order` (PositiveIntegerField, default=0) - Group ordering

## API Endpoints

### Task Management

#### 1. Task CRUD Operations
**Base URL**: `/api/tasks/`

**GET /api/tasks/**
- **Purpose**: List all accessible tasks with filtering and pagination
- **Query Parameters**: 
  - `personal` (boolean) - Filter to personal tasks only
  - `status` (string) - Filter by task status
  - `priority` (string) - Filter by priority level
  - `assigned_to` (int) - Filter by assignee
  - `project` (int) - Filter by project
  - `due_date_before` (datetime) - Tasks due before date
  - `due_date_after` (datetime) - Tasks due after date
  - `is_completed` (boolean) - Filter by completion status
  - `ordering` (string) - Sort order
- **Permissions**: Authenticated users (own tasks, assigned tasks, project tasks)
- **Response**:
```json
{
  "count": 25,
  "next": "http://api/tasks/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Implement user authentication",
      "description": "Add JWT-based authentication system",
      "status": "in_progress",
      "priority": "high",
      "due_date": "2024-01-20T10:00:00Z",
      "project": 1,
      "project_name": "Web Application",
      "assigned_to": 2,
      "assigned_to_email": "john@example.com",
      "is_completed": false,
      "is_overdue": false,
      "tags": ["backend", "security"],
      "created_at": "2024-01-15T09:00:00Z"
    }
  ]
}
```

**POST /api/tasks/**
- **Purpose**: Create a new task
- **Permissions**: Authenticated users
- **Request**:
```json
{
  "title": "New task title",
  "description": "Task description",
  "priority": "medium",
  "due_date": "2024-01-25T15:00:00Z",
  "project": 1,
  "assigned_to": 2,
  "estimated_hours": 4,
  "tags": ["frontend", "ui"]
}
```
- **Response**: Created task object (201 Created)

**GET /api/tasks/{id}/**
- **Purpose**: Retrieve specific task with checklist items
- **Permissions**: Task creator, assignee, or project owner
- **Response**: Task object with extended details including checklist

**PUT/PATCH /api/tasks/{id}/**
- **Purpose**: Update specific task
- **Permissions**: Task creator, assignee, or project owner
- **Request**: Partial or complete task data
- **Response**: Updated task object

**DELETE /api/tasks/{id}/**
- **Purpose**: Delete specific task
- **Permissions**: Task creator or project owner
- **Response**: `204 No Content`

#### 2. Task Actions

**POST /api/tasks/{id}/toggle-completion/**
- **Purpose**: Toggle task completion status
- **Permissions**: Task creator, assignee, or project owner
- **Request**: No body required
- **Response**:
```json
{
  "task": { /* task object */ },
  "message": "Task completed"
}
```

**POST /api/tasks/{id}/complete/**
- **Purpose**: Mark task as completed
- **Permissions**: Task creator, assignee, or project owner
- **Request**: No body required
- **Response**: Updated task object

**POST /api/tasks/{id}/snooze/**
- **Purpose**: Snooze task until specified datetime
- **Permissions**: Task creator, assignee, or project owner
- **Request**:
```json
{
  "until": "2024-01-22T09:00:00Z"
}
```
- **Response**: Updated task object

### Backlog Management

#### 1. BacklogItem CRUD Operations
**Base URL**: `/api/tasks/backlog/`

**GET /api/tasks/backlog/**
- **Purpose**: List user's backlog items
- **Query Parameters**:
  - `source` (string) - Filter by source (personal/work/client)
  - `is_converted` (boolean) - Filter by conversion status
- **Permissions**: Authenticated users (own items only)
- **Response**:
```json
{
  "count": 10,
  "results": [
    {
      "id": 1,
      "title": "Research new framework",
      "source": "personal",
      "created_by": 1,
      "created_by_name": "John Doe",
      "is_converted": false,
      "converted_to_task": null,
      "created_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

**POST /api/tasks/backlog/**
- **Purpose**: Create new backlog item
- **Permissions**: Authenticated users
- **Request**:
```json
{
  "title": "New idea or task",
  "source": "work"
}
```
- **Response**: Created backlog item (201 Created)

**POST /api/tasks/backlog/{id}/convert_to_task/**
- **Purpose**: Convert backlog item to full task
- **Permissions**: Backlog item creator
- **Request**:
```json
{
  "description": "Detailed task description",
  "priority": "high",
  "due_date": "2024-01-25T15:00:00Z",
  "project": 1,
  "estimated_hours": 6
}
```
- **Response**:
```json
{
  "task": { /* created task object */ },
  "backlog_item": { /* updated backlog item */ }
}
```

### Task Checklist Management

#### 1. TaskChecklist CRUD Operations
**Base URL**: `/api/tasks/{task_id}/checklist/`

**GET /api/tasks/{task_id}/checklist/**
- **Purpose**: List checklist items for a task
- **Permissions**: Task creator, assignee, or project owner
- **Response**:
```json
[
  {
    "id": 1,
    "title": "Set up database schema",
    "is_completed": true,
    "completed_at": "2024-01-16T14:30:00Z",
    "position": 0,
    "created_at": "2024-01-15T10:00:00Z"
  }
]
```

**POST /api/tasks/{task_id}/checklist/**
- **Purpose**: Create new checklist item
- **Permissions**: Task creator, assignee, or project owner
- **Request**:
```json
{
  "title": "Complete unit tests",
  "position": 1
}
```
- **Response**: Created checklist item (201 Created)

**POST /api/tasks/{task_id}/checklist/{id}/toggle_completion/**
- **Purpose**: Toggle checklist item completion
- **Permissions**: Task creator, assignee, or project owner
- **Request**: No body required
- **Response**:
```json
{
  "message": "Checklist item marked as completed",
  "checklist_item": { /* updated checklist item */ }
}
```

### Team Task Management

#### 1. Team Task Listing
**Base URL**: `/api/tasks/teams/{team_id}/`

**GET /api/tasks/teams/{team_id}/**
- **Purpose**: List tasks assigned to specific team
- **Query Parameters**: Same filtering options as main task list
- **Permissions**: Authenticated users
- **Response**: Paginated list of team tasks

## Serializers and Data Validation

### TaskSerializer
**Purpose**: Standard task serialization with read-only computed fields

**Fields**:
- All model fields plus computed properties
- `is_overdue` - Read-only overdue status
- `project_name` - Read-only project name
- `assigned_to_email` - Read-only assignee email
- `tags` - Serialized as string array

**Validation Rules**:
- `title` is required and max 200 characters
- `due_date` must be valid datetime format
- `estimated_hours` must be positive integer
- `priority` must be valid choice

### TaskCreateSerializer
**Purpose**: Task creation with tag support and relationship validation

**Fields**:
- Core task fields for creation
- `dependencies` - Validated task IDs
- `assigned_users` - Validated user IDs
- `assigned_teams` - Validated department IDs
- `tags` - Tag list serialization

**Validation Rules**:
- `project` must exist and be accessible to user
- `assigned_to` must be valid user
- `dependencies` cannot create circular references
- `due_date` cannot be in the past for new tasks

### TaskUpdateSerializer
**Purpose**: Task updates with status and completion handling

**Fields**:
- Updatable task fields
- `status` and `is_completed` with validation
- `actual_hours` tracking

**Validation Rules**:
- Cannot change `created_by` or `project` after creation
- `actual_hours` must not exceed reasonable limits
- Status transitions must follow business rules

### BacklogItemSerializer
**Purpose**: Simple backlog item serialization

**Fields**:
- `title`, `source`, `created_by_name`
- `is_converted`, `converted_task_title`
- Read-only conversion status

**Validation Rules**:
- `title` is required, max 255 characters
- `source` must be valid choice

### TaskChecklistSerializer
**Purpose**: Checklist item serialization

**Fields**:
- `title`, `is_completed`, `position`
- `completed_at` (read-only)

**Validation Rules**:
- `title` is required, max 255 characters
- `position` must be non-negative integer

## Data Validation Rules

### Task Validation
- Title cannot be empty or only whitespace
- Due date must be valid datetime if provided
- Estimated hours/minutes must be positive integers
- Priority must be one of: low, medium, high, urgent
- Status must be valid TaskStatus choice
- Cannot assign task to non-existent users/teams

### Business Logic Constraints
- Completed tasks automatically get `completed_at` timestamp
- Completing task updates project completion percentage
- Moving task to Kanban column updates task status
- Cannot delete tasks with dependent tasks
- Subtasks inherit project from parent task
- WIP limits enforced on Kanban columns

## Permission System Integration

### Access Control
- Users can access tasks they created, are assigned to, or belong to their projects
- Team members can access tasks assigned to their department
- Project owners have full access to all project tasks
- No cross-user access to personal tasks

### Permission Requirements by Endpoint
| Endpoint | Required Permission | Notes |
|----------|-------------------|-------|
| GET /tasks/ | IsAuthenticated | Filtered by user access |
| POST /tasks/ | IsAuthenticated | Auto-assigned to creator |
| PUT /tasks/{id}/ | Task access | Creator, assignee, or project owner |
| DELETE /tasks/{id}/ | Task ownership | Creator or project owner only |
| POST /tasks/{id}/toggle-completion/ | Task access | Creator, assignee, or project owner |
| GET /backlog/ | IsAuthenticated | Own items only |
| POST /backlog/ | IsAuthenticated | Auto-assigned to creator |
| GET /checklist/ | Task access | Based on parent task permissions |

## Error Handling

### Common Error Responses
```json
{
  "error": "Validation failed",
  "details": {
    "title": ["This field is required"],
    "due_date": ["Invalid datetime format"],
    "assigned_to": ["User does not exist"]
  }
}
```

### HTTP Status Codes
- 200: Success
- 201: Created
- 400: Bad Request (validation errors)
- 401: Unauthorized (not authenticated)
- 403: Forbidden (permission denied)
- 404: Not Found (task/resource not found)
- 409: Conflict (circular dependency, WIP limit exceeded)
- 500: Internal Server Error

### App-Specific Error Codes
| Error Code | Description | Resolution |
|------------|-------------|------------|
| TASK_001 | Circular dependency detected | Remove conflicting dependencies |
| TASK_002 | WIP limit exceeded | Move tasks or increase limit |
| TASK_003 | Invalid status transition | Use valid status progression |
| TASK_004 | Cannot delete task with dependencies | Remove dependencies first |

## Performance Considerations

### Query Optimization
- Database indexes on frequently queried fields (status, due_date, assigned_to)
- select_related() for foreign key relationships
- prefetch_related() for many-to-many relationships
- Efficient filtering in get_queryset() methods

### Pagination
- Default page size: 20 tasks
- Maximum page size: 100 tasks
- Pagination parameters: `page`, `page_size`

### Filtering and Search
- **Filterable fields**: status, priority, assigned_to, project, due_date, is_completed
- **Searchable fields**: title, description, tags
- **Ordering fields**: created_at, updated_at, due_date, priority, status

## Security Features

### Authentication
- JWT token authentication required
- Session-based authentication supported
- Token refresh mechanism

### Authorization
- Object-level permissions for task access
- Team-based access control
- Project ownership validation

### Data Protection
- User data isolation (no cross-user access)
- Input sanitization for all text fields
- SQL injection prevention through ORM
- XSS protection in serialized output

## Integration Points

### Dependencies on Other Apps
- **Projects**: Task-project relationships, milestone tracking
- **Users**: Task assignment, ownership, team membership
- **Accounts**: Department-based team assignments
- **Comments**: Generic relation for task comments
- **Core**: BaseModel inheritance for common fields

### External Services
- **Tagging System**: django-taggit for task categorization
- **Celery**: Background task processing (future enhancement)
- **Email Notifications**: Task assignment and due date alerts

## Testing

### Test Coverage
- Model tests: 95% coverage
- Serializer tests: 90% coverage
- View tests: 88% coverage
- Integration tests: 85% coverage

### Key Test Scenarios
- Task CRUD operations with permission validation
- Backlog item conversion to tasks
- Checklist item management and completion tracking
- Kanban board task movement and status updates
- Team task assignment and access control
- Task dependency management and circular reference prevention
- Due date and overdue status calculations
- Tag management and filtering

## Configuration

### Settings
```python
# Task-specific settings
TASK_DEFAULT_PAGE_SIZE = 20
TASK_MAX_PAGE_SIZE = 100
TASK_ENABLE_NOTIFICATIONS = True
TASK_WIP_LIMIT_DEFAULT = 5
```

### Environment Variables
- `TASK_NOTIFICATION_EMAIL`: Email for task notifications
- `TASK_DEBUG_MODE`: Enable detailed task logging

## Deployment Notes

### Database Migrations
- Migration 0001: Initial task models
- Migration 0002: Added Kanban board support
- Migration 0003: Added backlog and checklist models
- Migration 0004: Added performance indexes
- Migration 0005: Added task dependencies and subtasks

### Static Files
- No static files required for backend API
- Frontend assets handled separately

### Background Tasks
- Task notification emails (planned)
- Recurring task creation (planned)
- Task analytics aggregation (planned)

## Monitoring and Logging

### Key Metrics
- Task creation rate: Tasks created per day/week
- Task completion rate: Percentage of tasks completed on time
- Overdue task count: Number of tasks past due date
- User productivity: Tasks completed per user per day

### Log Levels
- INFO: Task creation, completion, assignment changes
- WARNING: Approaching due dates, WIP limit warnings
- ERROR: Failed task operations, permission violations

## Troubleshooting

### Common Issues
| Issue | Symptoms | Solution |
|-------|----------|----------|
| Tasks not appearing | Empty task list for user | Check task assignment and project access |
| Cannot complete task | 403 Forbidden on completion | Verify user has task access permissions |
| Kanban drag-drop fails | Tasks don't move between columns | Check column permissions and WIP limits |
| Backlog conversion fails | 400 error on conversion | Validate project access and required fields |

### Debug Mode
- Enable with: `TASK_DEBUG_MODE = True`
- Additional logging available in Django logs
- Detailed permission check logging

## Future Enhancements

### Planned Features
- **Task Templates**: Reusable task templates for common workflows (Q2 2024)
- **Time Tracking**: Built-in time tracking with start/stop functionality (Q2 2024)
- **Advanced Notifications**: Email, SMS, and in-app notifications (Q3 2024)
- **Task Analytics**: Productivity insights and reporting (Q3 2024)
- **Mobile App**: Native mobile application (Q4 2024)

### Technical Debt
- Refactor legacy TaskGroup model usage
- Implement proper task archiving system
- Add comprehensive audit logging
- Optimize complex queries with database views
- Add proper caching layer for frequently accessed data

---

## Documentation Maintenance

**Last Updated**: January 15, 2024
**Version**: 1.2.0
**Maintainer**: Development Team

### Change Log
| Date | Version | Changes |
|------|---------|---------|
| 2024-01-15 | 1.2.0 | Added backlog and checklist functionality |
| 2024-01-10 | 1.1.0 | Added Kanban board support |
| 2024-01-05 | 1.0.0 | Initial comprehensive documentation |
