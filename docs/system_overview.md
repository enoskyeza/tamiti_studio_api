# Tamiti Studio System Documentation
**"Your Office, Anywhere" - Complete Business Management in Your Pocket**

## Overview
Tamiti Studio is a comprehensive business management platform that brings your entire office operations into a unified, mobile-first system. It provides modular applications that can be easily enabled or disabled through the admin panel, offering fine-grained control over features and permissions.

---

## Application Summary

1. **Finance App** - Complete financial management with accounts, transactions, budgets, and debt tracking
2. **Field App** - Sales team and lead management with territory tracking and customer relationship tools
3. **Tasks App** - Advanced task management with backlogs, checklists, and project integration
4. **Projects App** - Project lifecycle management with milestones, budgets, and team collaboration
5. **Planner App** - Time blocking, scheduling, and availability management with break policies
6. **Chatrooms App** - Internal communication with channels, direct messaging, and file sharing
7. **Social App** - Social media content planning, scheduling, and approval workflows
8. **Notifications App** - System-wide notification management and delivery
9. **Assistants App** - Virtual assistant commands and automated responses
10. **Content App** - Document and media management with version control
11. **Permissions App** - Fine-grained access control and role-based permissions
12. **Accounts App** - Staff management, departments, and organizational structure
13. **Users App** - User profiles, authentication, and personal settings

---

## Detailed Application Overview

### 1. Finance App
**Purpose**: Complete financial management and accounting system

**Core Features**:
- **Account Management**: Multiple account types (personal, company, savings, checking)
- **Transaction Tracking**: Income, expenses, transfers with categorization
- **Budget Management**: Budget creation, tracking, and variance analysis
- **Debt Management**: Personal and business debt tracking with payment schedules
- **Financial Reporting**: Balance sheets, income statements, cash flow reports
- **Multi-currency Support**: Handle different currencies with exchange rates

**Key Data Structures**:
- `Account`: Financial accounts with balances and metadata
- `Transaction`: Financial transactions with categories and descriptions
- `Budget`: Budget plans with periods and categories
- `PersonalDebt`: Debt tracking with interest calculations
- `Category`: Transaction categorization system

**API Endpoints**:
- `/api/finance/accounts/` - Account CRUD operations
- `/api/finance/transactions/` - Transaction management
- `/api/finance/budgets/` - Budget planning and tracking
- `/api/finance/debts/` - Debt management
- `/api/finance/reports/` - Financial reporting

### 2. Field App
**Purpose**: Sales team management and lead tracking system

**Core Features**:
- **Lead Management**: Capture, qualify, and track sales leads
- **Territory Management**: Zone-based lead assignment and tracking
- **Sales Pipeline**: Lead stages from prospect to conversion
- **Follow-up Tracking**: Scheduled follow-ups and reminders
- **Performance Analytics**: Sales rep performance and conversion metrics
- **Document Management**: Lead-related documents and contracts

**Key Data Structures**:
- `Lead`: Business leads with contact information and status
- `Zone`: Geographic territories for lead assignment
- `LeadAction`: Actions taken on leads (calls, visits, emails)
- `Visit`: Field visits with outcomes and notes
- `FollowUp`: Scheduled follow-up activities

**API Endpoints**:
- `/api/field/leads/` - Lead management
- `/api/field/zones/` - Territory management
- `/api/field/visits/` - Visit tracking
- `/api/field/actions/` - Lead actions
- `/api/field/reports/` - Sales analytics

### 3. Tasks App
**Purpose**: Advanced task and project management system

**Core Features**:
- **Task Management**: Create, assign, and track tasks with priorities
- **Backlog System**: Quick idea capture with conversion to detailed tasks
- **Checklist Support**: Sub-tasks and checklist items within tasks
- **Kanban Boards**: Visual task management with drag-and-drop
- **Dependencies**: Task dependencies and scheduling
- **Time Tracking**: Estimated vs actual time tracking
- **Team Collaboration**: Task assignment and team coordination

**Key Data Structures**:
- `Task`: Main task entity with status, priority, and assignments
- `BacklogItem`: Quick capture items for later conversion
- `TaskChecklist`: Sub-items within tasks
- `KanbanBoard`: Visual task organization
- `TaskGroup`: Task categorization and grouping

**API Endpoints**:
- `/api/tasks/` - Task CRUD operations
- `/api/tasks/backlog/` - Backlog management
- `/api/tasks/{id}/checklists/` - Task checklist management
- `/api/tasks/kanban/` - Kanban board operations
- `/api/tasks/teams/{id}/` - Team task views

### 4. Projects App
**Purpose**: Project lifecycle and portfolio management

**Core Features**:
- **Project Planning**: Project creation with timelines and budgets
- **Milestone Tracking**: Key deliverables and checkpoint management
- **Resource Allocation**: Team member assignment and workload management
- **Budget Tracking**: Project costs and budget variance monitoring
- **Progress Reporting**: Project status and completion tracking
- **Client Management**: Client communication and project visibility

**Key Data Structures**:
- `Project`: Main project entity with timeline and budget
- `Milestone`: Project milestones and deliverables
- `ProjectMember`: Team member assignments and roles
- `ProjectBudget`: Financial planning and tracking

**API Endpoints**:
- `/api/projects/` - Project management
- `/api/projects/{id}/milestones/` - Milestone tracking
- `/api/projects/{id}/members/` - Team management
- `/api/projects/{id}/budget/` - Budget tracking

### 5. Planner App
**Purpose**: Time management and scheduling system

**Core Features**:
- **Time Blocking**: Calendar-based time allocation
- **Availability Management**: Work hours and availability templates
- **Break Policies**: Pomodoro and break scheduling
- **Calendar Integration**: Event and meeting management
- **Resource Scheduling**: Room and resource booking
- **Workload Balancing**: Team capacity planning

**Key Data Structures**:
- `TimeBlock`: Scheduled time slots for tasks and activities
- `AvailabilityTemplate`: Weekly availability patterns
- `BreakPolicy`: Break and focus time configurations
- `CalendarEvent`: Meetings and appointments

**API Endpoints**:
- `/api/planner/timeblocks/` - Time block management
- `/api/planner/availability/` - Availability templates
- `/api/planner/calendar/` - Calendar events
- `/api/planner/breaks/` - Break policy management

### 6. Chatrooms App
**Purpose**: Internal communication and collaboration

**Core Features**:
- **Channel Communication**: Team channels and group discussions
- **Direct Messaging**: One-on-one conversations
- **File Sharing**: Document and media sharing in conversations
- **Message Threading**: Organized conversation threads
- **Notification Integration**: Real-time message notifications
- **Message Search**: Full-text search across conversations

**Key Data Structures**:
- `Channel`: Communication channels (public/private)
- `Message`: Chat messages with threading support
- `Thread`: Message conversation threads
- `ChannelMember`: Channel membership and permissions

**API Endpoints**:
- `/api/chat/channels/` - Channel management
- `/api/chat/messages/` - Message operations
- `/api/chat/threads/` - Thread management
- `/api/chat/members/` - Channel membership

### 7. Social App
**Purpose**: Social media content management and scheduling

**Core Features**:
- **Content Planning**: Social media post creation and scheduling
- **Multi-platform Support**: Facebook, Twitter, LinkedIn, Instagram
- **Approval Workflows**: Content review and approval processes
- **Scheduling**: Automated post publishing
- **Analytics Integration**: Social media performance tracking
- **Team Collaboration**: Content creation and review workflows

**Key Data Structures**:
- `SocialPost`: Social media posts with platform targeting
- `PostComment`: Internal comments and feedback
- `PostSchedule`: Publishing schedules and automation

**API Endpoints**:
- `/api/social/posts/` - Post management
- `/api/social/schedule/` - Scheduling operations
- `/api/social/analytics/` - Performance metrics

### 8. Notifications App
**Purpose**: System-wide notification management

**Core Features**:
- **Multi-channel Delivery**: Email, SMS, push, in-app notifications
- **Template Management**: Notification templates and personalization
- **Delivery Tracking**: Notification status and delivery confirmation
- **User Preferences**: Notification settings and opt-out management
- **Bulk Notifications**: Mass notification campaigns
- **Integration Hooks**: API webhooks for external systems

**Key Data Structures**:
- `Notification`: Individual notification records
- `NotificationTemplate`: Reusable notification templates
- `NotificationPreference`: User notification settings
- `DeliveryLog`: Notification delivery tracking

**API Endpoints**:
- `/api/notifications/` - Notification management
- `/api/notifications/templates/` - Template management
- `/api/notifications/preferences/` - User preferences
- `/api/notifications/send/` - Notification sending

### 9. Assistants App
**Purpose**: Virtual assistant and automation system

**Core Features**:
- **Command Processing**: Natural language command interpretation
- **Automated Responses**: Pre-configured response templates
- **API Integration**: Connect commands to system functions
- **Context Awareness**: User and session context handling
- **Learning Capabilities**: Command usage analytics and optimization
- **Multi-modal Support**: Text, voice, and action-based interactions

**Key Data Structures**:
- `VACommand`: Virtual assistant commands and triggers
- `DefaultResponse`: Fallback responses for unrecognized commands
- `CommandLog`: Usage tracking and analytics

**API Endpoints**:
- `/api/assistants/commands/` - Command management
- `/api/assistants/process/` - Command processing
- `/api/assistants/responses/` - Response management

### 10. Content App
**Purpose**: Document and media management system

**Core Features**:
- **File Management**: Upload, organize, and share files
- **Version Control**: Document versioning and history
- **Access Control**: File-level permissions and sharing
- **Search Capabilities**: Full-text search across documents
- **Collaboration**: Document commenting and review workflows
- **Storage Integration**: Cloud storage and CDN integration

**Key Data Structures**:
- `Document`: File metadata and storage information
- `DocumentVersion`: Version history and changes
- `DocumentShare`: Sharing permissions and access logs
- `DocumentComment`: Collaborative feedback and reviews

**API Endpoints**:
- `/api/content/documents/` - Document management
- `/api/content/versions/` - Version control
- `/api/content/shares/` - Sharing management
- `/api/content/search/` - Content search

### 11. Permissions App
**Purpose**: Fine-grained access control system

**Core Features**:
- **Role-based Access**: Hierarchical role and permission management
- **Object-level Permissions**: Granular access control per resource
- **Permission Inheritance**: Role-based permission cascading
- **Audit Logging**: Permission change tracking and compliance
- **Dynamic Permissions**: Context-aware permission evaluation
- **API Security**: Endpoint-level access control

**Key Data Structures**:
- `Permission`: Individual permission definitions
- `Role`: User roles with permission sets
- `UserPermission`: User-specific permission overrides
- `PermissionLog`: Audit trail for permission changes

**API Endpoints**:
- `/api/permissions/roles/` - Role management
- `/api/permissions/users/` - User permissions
- `/api/permissions/check/` - Permission validation
- `/api/permissions/audit/` - Audit logs

### 12. Accounts App
**Purpose**: Staff and organizational management

**Core Features**:
- **Staff Management**: Employee profiles and organizational structure
- **Department Organization**: Hierarchical department management
- **Role Assignment**: Job roles and responsibility management
- **Onboarding Workflows**: New employee setup processes
- **Performance Tracking**: Staff performance and review management
- **Organizational Charts**: Visual organization structure

**Key Data Structures**:
- `Department`: Organizational departments and teams
- `Designation`: Job titles and roles
- `Branch`: Physical locations and branches
- `StaffProfile`: Extended employee information
- `Referral`: Employee referral tracking

**API Endpoints**:
- `/api/accounts/departments/` - Department management
- `/api/accounts/staff/` - Staff management
- `/api/accounts/roles/` - Role management
- `/api/accounts/branches/` - Branch management

### 13. Users App
**Purpose**: User authentication and profile management

**Core Features**:
- **User Authentication**: Login, registration, and password management
- **Profile Management**: User profiles and personal information
- **Preference Settings**: User customization and preferences
- **Security Features**: Two-factor authentication and security settings
- **Activity Tracking**: User activity logs and session management
- **Integration Support**: SSO and external authentication

**Key Data Structures**:
- `User`: Core user authentication and profile
- `UserProfile`: Extended user information and preferences
- `UserSession`: Session management and tracking
- `UserActivity`: Activity logging and analytics

**API Endpoints**:
- `/api/users/auth/` - Authentication operations
- `/api/users/profile/` - Profile management
- `/api/users/preferences/` - User settings
- `/api/users/activity/` - Activity tracking

---

## System Administration

### Admin Roles
1. **System Administrator (Super User)**
   - Full system access and control
   - App enable/disable capabilities
   - Global settings management
   - User and permission management
   - System monitoring and maintenance

2. **App Administrator**
   - Limited administrative rights within assigned apps
   - User management within their scope
   - App-specific configuration
   - Reporting and analytics access
   - No app enable/disable permissions

### Admin Panel Features
- **App Management**: Enable/disable applications system-wide
- **User Management**: Create, modify, and deactivate user accounts
- **Permission Control**: Fine-grained permission assignment
- **System Settings**: Global configuration and preferences
- **Monitoring Dashboard**: System health and usage analytics
- **Audit Logs**: Comprehensive activity tracking

---

## Frontend Navigation Structure

### Mobile-First Design Approach
The system prioritizes mobile experience with responsive design patterns.

### Navigation States

#### Large Screens (Desktop/Tablet)
**Side Navigation** with three states:
1. **Hidden**: Only hamburger menu visible in top nav
2. **Collapsed**: Icons only, minimal width
3. **Expanded**: Icons with labels, full navigation

#### Small Screens (Mobile)
**Bottom Navigation** (fixed position):
- 4 primary app icons
- "More" button (3-dot stack) for additional apps
- Content scrolls between top and bottom navigation bars

### Navigation Structure
```
Top Navigation Bar
├── Logo/Brand
├── Hamburger Menu (large screens)
├── Search Bar
├── Notifications
└── User Menu Dropdown
    ├── Profile Settings
    ├── Admin Dashboard (if authorized)
    ├── System Settings
    └── Logout

Side/Bottom Navigation (App-specific)
├── Finance
│   ├── Dashboard
│   ├── Accounts
│   ├── Transactions
│   ├── Budgets
│   └── Reports
├── Field
│   ├── Leads
│   ├── Territories
│   ├── Visits
│   └── Analytics
├── Tasks
│   ├── My Tasks
│   ├── Backlog
│   ├── Kanban
│   └── Team Tasks
├── Projects
│   ├── Active Projects
│   ├── Planning
│   ├── Resources
│   └── Reports
├── Planner
│   ├── Calendar
│   ├── Time Blocks
│   ├── Availability
│   └── Breaks
├── Social
│   ├── Content Calendar
│   ├── Drafts
│   ├── Scheduled
│   └── Analytics
└── [Additional Apps...]

Global Features (Not in Navigation)
├── Chat Bubble (floating, bottom-right)
│   ├── Unread message counter
│   ├── Quick access to conversations
│   └── Available on all screens
└── Admin Access (user dropdown only)
```

### UI/UX Specifications

#### Color Palette (RGB Values)
- **Primary**: `69 92 141` (#455c8d) - Main brand color
- **Secondary**: `156 179 128` (#9cb380) - Supporting actions
- **Accent**: `214 163 25` (#d6a319) - Highlights and CTAs
- **Dark**: `12 47 90` (#0c2f5a) - Text and dark elements
- **Light**: `251 251 255` (#fbfbff) - Backgrounds and surfaces

#### Design Principles
- **Mobile-First**: Responsive design starting from mobile
- **Clean & Modern**: Minimalist interface with clear hierarchy
- **Accessibility**: WCAG 2.1 AA compliance
- **Performance**: Optimized loading and smooth interactions
- **Consistency**: Unified design language across all apps

#### Component Standards
- **Cards**: Rounded corners, subtle shadows
- **Buttons**: Clear hierarchy (primary, secondary, accent)
- **Forms**: Inline validation, clear error states, tool tips with sonner
- **Tables**: Responsive, sortable, filterable
- **Modals**: Centered, backdrop blur, escape key support
- **Loading States**: Skeleton screens and progress indicators

---

## Technical Architecture

### Backend Framework
- **Django 5.2.4** with Django REST Framework
- **PostgreSQL/SQLite** database support
- **Redis** for caching and sessions
- **Celery** for background tasks

### API Design
- **RESTful APIs** with consistent patterns
- **JWT Authentication** with refresh tokens
- **Pagination** for large datasets
- **Filtering & Searching** across all endpoints
- **API Documentation** with OpenAPI/Swagger

### Security Features
- **Role-based Access Control** (RBAC)
- **Object-level Permissions**
- **API Rate Limiting**
- **CSRF Protection**
- **SQL Injection Prevention**
- **XSS Protection**

### Performance Optimization
- **Database Query Optimization**
- **Caching Strategies**
- **CDN Integration**
- **Image Optimization**
- **Lazy Loading**
- **Background Processing**

---

## Deployment & Scaling

### Environment Support
- **Development**: Local development with hot reload
- **Staging**: Pre-production testing environment
- **Production**: Scalable production deployment

### Infrastructure
- **Containerized Deployment** (Docker)
- **Load Balancing** for high availability
- **Database Clustering** for performance
- **File Storage** (local/cloud options)
- **Monitoring & Logging** integration

### Backup & Recovery
- **Automated Database Backups**
- **File Storage Backups**
- **Point-in-time Recovery**
- **Disaster Recovery Planning**

---

*This documentation serves as a comprehensive guide for frontend developers to understand the system architecture and build an intuitive, powerful user interface that leverages all backend capabilities while maintaining excellent user experience across all devices.*
