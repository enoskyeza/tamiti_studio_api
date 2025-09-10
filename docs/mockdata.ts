export interface User {
  id: string;
  name: string;
  email: string;
  avatar?: string;
  role: 'admin' | 'manager' | 'developer' | 'designer';
}

export interface Project {
  id: string;
  name: string;
  description: string;
  status: 'planning' | 'active' | 'paused' | 'review' | 'complete' | 'cancelled' | 'archived';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  startDate: string;
  endDate: string;
  budget?: number;
  clientName?: string;
  clientEmail?: string;
  tags: string[];
  assignedUsers: string[];
  progress: number;
  createdAt: string;
  updatedAt: string;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  status: 'todo' | 'in_progress' | 'review' | 'done';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  dueDate?: string;
  assignedUsers: string[];
  assignedTeams?: string[];
  projectId: string;
  estimatedHours?: number;
  actualHours?: number;
  dependencies?: string[];
  tags: string[];
  createdAt: string;
  updatedAt: string;
}

export interface Comment {
  id: string;
  content: string;
  author: string;
  authorName: string;
  timestamp: string;
  isInternal: boolean;
  parentId?: string;
  replies?: Comment[];
  attachments?: string[];
}

export interface ProjectComment extends Comment {
  projectId: string;
}

export interface TaskComment extends Comment {
  taskId: string;
}

export type ViewMode = 'kanban' | 'list';

export interface FilterOptions {
  status?: string[];
  priority?: string[];
  assignedUsers?: string[];
  projects?: string[];
  tags?: string[];
  dateRange?: {
    start: string;
    end: string;
  };
}