Tamiti Studio API Docs

Base URL

- Local: http://localhost:8000/api/

Interactive Docs

- Swagger UI: /api/docs/
- Redoc: /api/redoc/
- OpenAPI (JSON): /api/schema/

Auth

- Login: POST /users/login/
  - Body: { "email": string, "password": string }
  - Returns: { access: string, refresh (cookie) }
- Refresh: POST /users/token/refresh/
  - Uses refresh cookie; returns a new access token
- Current User: GET /users/me/
- Client usage: Send Authorization: Bearer <access_token>

Conventions

- Pagination: Paginated list responses generally follow `{ count, results }`
- Filtering: Common query params include `search`, `ordering`, app-specific filters
- Errors: DRF default error responses `{ detail }` or field-level validation errors

Modules & Key Endpoints

Users (/users)

- POST /users/register/
- POST /users/login/
- POST /users/token/refresh/
- GET /users/me/

Accounts (/accounts)

- GET /accounts/departments/
- GET /accounts/designations/
- GET /accounts/branches/
- GET /accounts/staff-roles/
- CRUD /accounts/staff-profiles/

Field (/field)

- CRUD /field/leads/
- CRUD /field/visits/
- GET /field/zones/
- Extra: /field/actions/ (lead-related actions)

Finance (/finance)

- CRUD /finance/parties/
- CRUD /finance/accounts/
- CRUD /finance/invoices/
- CRUD /finance/requisitions/
- CRUD /finance/transactions/
- CRUD /finance/payments/
- CRUD /finance/goals/

Projects (/projects)

- CRUD /projects/
- CRUD /projects/milestones/

Tasks (/tasks)

- CRUD /tasks/

Chatrooms (/chat)

- CRUD /chat/channels/
- CRUD /chat/direct-threads/
- List /chat/channel-messages/?channel=<id>
- POST /chat/channel-messages/
- POST /chat/direct-messages/

Assistants (/assistants)

- CRUD /assistants/
- POST /assistants/{id}/chat/

Notifications (/notifications)

- Namespaced URLs at /notifications/ (see app for details)

Dashboard (/dashboard)

- Aggregated metrics and dashboards

Content & Social (/content, /social)

- Structured content and social features

Example Requests

- Login
  curl -X POST \
    -H "Content-Type: application/json" \
    -d '{"email":"user@example.com","password":"password"}' \
    http://localhost:8000/api/users/login/

- List Leads
  curl -H "Authorization: Bearer $ACCESS" \
    http://localhost:8000/api/field/leads/

- Create Invoice
  curl -X POST \
    -H "Authorization: Bearer $ACCESS" \
    -H "Content-Type: application/json" \
    -d '{"number":"INV-001","party":1,"amount":1000}' \
    http://localhost:8000/api/finance/invoices/

Generating OpenAPI Schema

- Ensure your environment can import Django settings and apps
- From repo root:
  cd tamiti_studio
  ./venv/bin/python manage.py spectacular --file docs/openapi.yaml

Notes

- Swagger and Redoc are the source of truth; this document provides a curated overview.
- If you change serializers/viewsets, re-generate the schema.

