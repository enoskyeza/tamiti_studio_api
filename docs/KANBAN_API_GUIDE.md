# Kanban Board API Guide

This guide provides comprehensive documentation for implementing Kanban board functionality in the frontend application.

## Overview

The Kanban system consists of:
- **KanbanBoard**: Container for a project's Kanban board
- **KanbanColumn**: Individual columns (To Do, In Progress, Review, Done)
- **Task**: Tasks that can be moved between columns

## API Endpoints

### 1. Kanban Board Management

#### Get Project's Kanban Board
```
GET /api/tasks/kanban/projects/{project_id}/board/
```
**Response:**
```json
{
  "id": 1,
  "name": "Project Board",
  "project": 1,
  "project_name": "My Project",
  "columns": [
    {
      "id": 1,
      "name": "To Do",
      "status_mapping": "todo",
      "order": 0,
      "color": "#EF4444",
      "wip_limit": null,
      "task_count": 5,
      "is_wip_exceeded": false,
      "tasks": [
        {
          "id": 1,
          "title": "Task 1",
          "status": "todo",
          "priority": "high",
          "assignedUsers": [1, 2],
          "kanban_position": 0
        }
      ]
    }
  ]
}
```

#### Initialize Kanban Board for Project
```
POST /api/tasks/kanban/projects/{project_id}/initialize/
```
Creates a Kanban board and assigns existing tasks to appropriate columns based on their status.

#### List All Kanban Boards
```
GET /api/tasks/kanban/boards/
```

#### Create Kanban Board
```
POST /api/tasks/kanban/boards/
```
**Request Body:**
```json
{
  "name": "Custom Board Name",
  "project": 1
}
```

### 2. Column Management

#### List Columns for a Board
```
GET /api/tasks/kanban/boards/{board_id}/columns/
```

#### Create New Column
```
POST /api/tasks/kanban/boards/{board_id}/columns/
```
**Request Body:**
```json
{
  "name": "Custom Column",
  "status_mapping": "in_progress",
  "order": 2,
  "color": "#8B5CF6",
  "wip_limit": 3
}
```

#### Update Column
```
PUT /api/tasks/kanban/columns/{column_id}/
PATCH /api/tasks/kanban/columns/{column_id}/
```

### 3. Task Movement (Drag & Drop)

#### Move Task to Different Column
```
POST /api/tasks/kanban/tasks/{task_id}/move/
```
**Request Body:**
```json
{
  "target_column_id": 2,
  "position": 1
}
```
- `position` is optional. If not provided, task moves to end of column
- Task status automatically updates based on column's `status_mapping`

#### Reorder Task Within Same Column
```
POST /api/tasks/kanban/tasks/{task_id}/reorder/
```
**Request Body:**
```json
{
  "new_position": 3
}
```

## Frontend Implementation Guide

### 1. Basic Kanban Board Setup

```typescript
interface KanbanBoard {
  id: number;
  name: string;
  project: number;
  project_name: string;
  columns: KanbanColumn[];
}

interface KanbanColumn {
  id: number;
  name: string;
  status_mapping: string;
  order: number;
  color: string;
  wip_limit?: number;
  task_count: number;
  is_wip_exceeded: boolean;
  tasks: Task[];
}

// Fetch board data
const fetchKanbanBoard = async (projectId: number): Promise<KanbanBoard> => {
  const response = await fetch(`/api/tasks/kanban/projects/${projectId}/board/`);
  return response.json();
};
```

### 2. Drag and Drop Implementation

```typescript
// Handle task drop between columns
const handleTaskDrop = async (
  taskId: number,
  targetColumnId: number,
  newPosition: number
) => {
  try {
    const response = await fetch(`/api/tasks/kanban/tasks/${taskId}/move/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_column_id: targetColumnId,
        position: newPosition
      })
    });
    
    if (response.ok) {
      // Refresh board data or update state optimistically
      refreshBoard();
    }
  } catch (error) {
    console.error('Failed to move task:', error);
  }
};

// Handle task reorder within same column
const handleTaskReorder = async (taskId: number, newPosition: number) => {
  try {
    const response = await fetch(`/api/tasks/kanban/tasks/${taskId}/reorder/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_position: newPosition })
    });
    
    if (response.ok) {
      refreshBoard();
    }
  } catch (error) {
    console.error('Failed to reorder task:', error);
  }
};
```

### 3. React Component Example

```tsx
import React, { useState, useEffect } from 'react';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';

const KanbanBoard: React.FC<{ projectId: number }> = ({ projectId }) => {
  const [board, setBoard] = useState<KanbanBoard | null>(null);

  useEffect(() => {
    fetchKanbanBoard(projectId).then(setBoard);
  }, [projectId]);

  const onDragEnd = async (result: any) => {
    if (!result.destination) return;

    const { draggableId, source, destination } = result;
    const taskId = parseInt(draggableId);

    if (source.droppableId === destination.droppableId) {
      // Reorder within same column
      await handleTaskReorder(taskId, destination.index);
    } else {
      // Move to different column
      const targetColumnId = parseInt(destination.droppableId);
      await handleTaskDrop(taskId, targetColumnId, destination.index);
    }
  };

  if (!board) return <div>Loading...</div>;

  return (
    <DragDropContext onDragEnd={onDragEnd}>
      <div className="kanban-board">
        {board.columns.map((column) => (
          <div key={column.id} className="kanban-column">
            <div className="column-header" style={{ backgroundColor: column.color }}>
              <h3>{column.name}</h3>
              <span className="task-count">{column.task_count}</span>
              {column.is_wip_exceeded && (
                <span className="wip-warning">WIP Limit Exceeded!</span>
              )}
            </div>
            
            <Droppable droppableId={column.id.toString()}>
              {(provided) => (
                <div
                  {...provided.droppableProps}
                  ref={provided.innerRef}
                  className="task-list"
                >
                  {column.tasks.map((task, index) => (
                    <Draggable
                      key={task.id}
                      draggableId={task.id.toString()}
                      index={index}
                    >
                      {(provided) => (
                        <div
                          ref={provided.innerRef}
                          {...provided.draggableProps}
                          {...provided.dragHandleProps}
                          className="task-card"
                        >
                          <h4>{task.title}</h4>
                          <p>{task.description}</p>
                          <div className="task-meta">
                            <span className={`priority ${task.priority}`}>
                              {task.priority}
                            </span>
                            {task.assignedUsers.length > 0 && (
                              <div className="assignees">
                                {task.assignedUsers.map(userId => (
                                  <UserAvatar key={userId} userId={userId} />
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </Draggable>
                  ))}
                  {provided.placeholder}
                </div>
              )}
            </Droppable>
          </div>
        ))}
      </div>
    </DragDropContext>
  );
};
```

### 4. View Mode Toggle

```typescript
// Implement view mode switching as per mockup
type ViewMode = 'kanban' | 'list';

const ProjectView: React.FC = () => {
  const [viewMode, setViewMode] = useState<ViewMode>('kanban');
  
  return (
    <div>
      <div className="view-toggle">
        <button 
          className={viewMode === 'kanban' ? 'active' : ''}
          onClick={() => setViewMode('kanban')}
        >
          Kanban
        </button>
        <button 
          className={viewMode === 'list' ? 'active' : ''}
          onClick={() => setViewMode('list')}
        >
          List
        </button>
      </div>
      
      {viewMode === 'kanban' ? (
        <KanbanBoard projectId={projectId} />
      ) : (
        <TaskList projectId={projectId} />
      )}
    </div>
  );
};
```

## Key Features Implemented

1. **Automatic Status Sync**: When tasks are moved between columns, their status automatically updates
2. **Position Management**: Tasks maintain their position within columns
3. **WIP Limits**: Columns can have Work In Progress limits with visual warnings
4. **Flexible Columns**: Custom columns can be created beyond the default ones
5. **Drag & Drop Support**: Full API support for drag-and-drop operations
6. **Mockup Compatibility**: All API responses include both Django field names and mockup-compatible aliases

## Error Handling

All endpoints return appropriate HTTP status codes:
- `200`: Success
- `400`: Bad Request (validation errors)
- `404`: Not Found (task/column/board doesn't exist)
- `403`: Forbidden (no permission)

Example error response:
```json
{
  "error": "Task not found"
}
```

## Performance Considerations

1. **Optimistic Updates**: Update UI immediately, then sync with server
2. **Debouncing**: Debounce rapid drag operations
3. **Pagination**: For large task lists, implement pagination within columns
4. **Caching**: Cache board data and update incrementally

This implementation provides a robust foundation for a modern Kanban board interface that matches the mockup requirements while maintaining Django best practices.
