# Personal Finance API Documentation

## Overview

The Personal Finance API extends the existing company finance system to support personal financial tracking. It provides endpoints for managing personal accounts, transactions, budgets, savings goals, and recurring transactions with detailed analytics and insights.

**Last Updated:** January 2024  
**Version:** 1.0  
**Status:** ✅ All endpoints tested and functional

## Base URL

All personal finance endpoints are prefixed with `/api/finance/personal/`

## Authentication

All endpoints require authentication. Include the authorization token in the request headers:

```
Authorization: Bearer <your-token>
```

## Data Models

### PersonalAccount

Personal accounts are user-owned financial accounts (bank accounts, mobile money, cash wallets).

**Fields:**
- `id` (integer): Unique identifier
- `name` (string): Account name
- `number` (string): Account number (optional)
- `type` (string): Account type (bank, mobile_money, cash, etc.)
- `balance` (decimal): Current balance
- `currency` (string): Currency code
- `is_active` (boolean): Whether account is active
- `created_at` (datetime): Creation timestamp
- `updated_at` (datetime): Last update timestamp

### PersonalTransaction

Individual income or expense transactions.

**Fields:**
- `id` (integer): Unique identifier
- `type` (string): Transaction type ('income' or 'expense')
- `amount` (decimal): Transaction amount
- `account` (object): Associated account details
- `description` (string): Transaction description
- `transaction_charge` (decimal): Additional charges/fees
- `income_source` (string): Source of income (if type is 'income')
- `expense_category` (string): Expense category (if type is 'expense')
- `reason` (string): Detailed reason for transaction
- `date` (datetime): Transaction date
- `reference_number` (string): Reference number (optional)
- `receipt_image` (file): Receipt image (optional)
- `tags` (array): Transaction tags
- `location` (string): Transaction location (optional)
- `notes` (string): Additional notes (optional)
- `is_recurring` (boolean): Whether transaction is recurring
- `created_at` (datetime): Creation timestamp
- `updated_at` (datetime): Last update timestamp

### PersonalBudget

Budget allocations for expense categories.

**Fields:**
- `id` (integer): Unique identifier
- `name` (string): Budget name
- `category` (string): Expense category
- `allocated_amount` (decimal): Budgeted amount
- `spent_amount` (decimal): Amount spent (calculated)
- `remaining_amount` (decimal): Remaining amount (calculated)
- `progress_percentage` (decimal): Progress percentage (calculated)
- `is_exceeded` (boolean): Whether budget is exceeded (calculated)
- `period` (string): Budget period ('weekly', 'monthly', 'quarterly', 'yearly')
- `start_date` (date): Budget start date
- `end_date` (date): Budget end date
- `description` (string): Budget description (optional)
- `is_active` (boolean): Whether budget is active
- `created_at` (datetime): Creation timestamp
- `updated_at` (datetime): Last update timestamp

### PersonalSavingsGoal

Savings goals with progress tracking.

**Fields:**
- `id` (integer): Unique identifier
- `name` (string): Goal name
- `target_amount` (decimal): Target amount to save
- `current_amount` (decimal): Current saved amount
- `remaining_amount` (decimal): Remaining amount (calculated)
- `progress_percentage` (decimal): Progress percentage (calculated)
- `is_achieved` (boolean): Whether goal is achieved (calculated)
- `target_date` (date): Target completion date (optional)
- `description` (string): Goal description (optional)
- `created_at` (datetime): Creation timestamp
- `updated_at` (datetime): Last update timestamp

### PersonalTransactionRecurring

Templates for recurring transactions.

**Fields:**
- `id` (integer): Unique identifier
- `name` (string): Recurring transaction name
- `type` (string): Transaction type ('income' or 'expense')
- `amount` (decimal): Transaction amount
- `account` (object): Associated account details
- `description` (string): Transaction description
- `transaction_charge` (decimal): Additional charges/fees
- `income_source` (string): Source of income (if type is 'income')
- `expense_category` (string): Expense category (if type is 'expense')
- `reason` (string): Detailed reason for transaction
- `frequency` (string): Frequency ('daily', 'weekly', 'monthly', 'yearly')
- `next_due_date` (date): Next due date
- `is_active` (boolean): Whether recurring transaction is active
- `created_at` (datetime): Creation timestamp
- `updated_at` (datetime): Last update timestamp

## API Endpoints

### Personal Accounts

#### List Personal Accounts
```
GET /api/finance/personal/accounts/
```

**Query Parameters:**
- `type`: Filter by account type
- `currency`: Filter by currency
- `is_active`: Filter by active status
- `search`: Search by name or number

**Response:**
```json
{
  "count": 3,
  "results": [
    {
      "id": 1,
      "name": "Main Bank Account",
      "number": "1234567890",
      "type": "bank",
      "balance": "5000.00",
      "currency": "UGX",
      "is_active": true,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### Create Personal Account
```
POST /api/finance/personal/accounts/
```

**Request Body:**
```json
{
  "name": "Savings Account",
  "number": "9876543210",
  "type": "bank",
  "currency": "UGX",
  "balance": "1000.00"
}
```

#### Get Account Details
```
GET /api/finance/personal/accounts/{id}/
```

#### Update Account
```
PUT /api/finance/personal/accounts/{id}/
PATCH /api/finance/personal/accounts/{id}/
```

#### Delete Account
```
DELETE /api/finance/personal/accounts/{id}/
```

### Personal Transactions

#### List Transactions
```
GET /api/finance/personal/transactions/
```

**Query Parameters:**
- `type`: Filter by transaction type ('income' or 'expense')
- `account`: Filter by account ID
- `income_source`: Filter by income source
- `expense_category`: Filter by expense category
- `date`: Filter by date
- `is_recurring`: Filter by recurring status
- `search`: Search in description, reason, reference number, location

**Response:**
```json
{
  "count": 10,
  "results": [
    {
      "id": 1,
      "type": "expense",
      "amount": "50.00",
      "account": {
        "id": 1,
        "name": "Main Bank Account"
      },
      "description": "Grocery shopping",
      "transaction_charge": "2.00",
      "expense_category": "food",
      "reason": "Weekly groceries",
      "date": "2024-01-15T10:30:00Z",
      "tags": ["groceries", "weekly"],
      "location": "Supermarket XYZ"
    }
  ]
}
```

#### Create Transaction
```
POST /api/finance/personal/transactions/
```

**Request Body:**
```json
{
  "type": "expense",
  "amount": "75.50",
  "account": 1,
  "description": "Fuel for car",
  "transaction_charge": "1.50",
  "expense_category": "transport",
  "reason": "Monthly fuel expense",
  "tags": ["fuel", "transport"],
  "location": "Shell Station"
}
```

#### Monthly Summary
```
GET /api/finance/personal/transactions/monthly_summary/?year=2024&month=1
```

**Response:**
```json
{
  "year": 2024,
  "month": 1,
  "total_income": "3000.00",
  "total_expenses": "1500.00",
  "total_transaction_charges": "45.00",
  "net_amount": "1500.00",
  "transaction_count": 25,
  "income_by_source": {
    "salary": "2500.00",
    "freelance": "500.00"
  },
  "expenses_by_category": {
    "food": "600.00",
    "transport": "400.00",
    "utilities": "300.00",
    "entertainment": "200.00"
  }
}
```

#### Spending Insights
```
GET /api/finance/personal/transactions/spending_insights/?days=30
```

**Response:**
```json
{
  "period_days": 30,
  "start_date": "2024-01-01",
  "end_date": "2024-01-30",
  "total_income": "3000.00",
  "total_expenses": "2200.00",
  "average_daily_expense": "73.33",
  "highest_expense_day": {
    "date": "2024-01-15",
    "amount": "250.00"
  },
  "top_expense_categories": [
    {"category": "food", "amount": "800.00", "percentage": 36.4},
    {"category": "transport", "amount": "600.00", "percentage": 27.3}
  ],
  "spending_trend": "increasing"
}
```

#### Category Breakdown
```
GET /api/finance/personal/transactions/category_breakdown/?days=30
```

### Personal Budgets

#### List Budgets
```
GET /api/finance/personal/budgets/
```

#### Create Budget
```
POST /api/finance/personal/budgets/
```

**Request Body:**
```json
{
  "name": "Monthly Food Budget",
  "category": "food",
  "allocated_amount": "800.00",
  "period": "monthly",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31",
  "description": "Budget for monthly food expenses"
}
```

#### Budget Progress
```
GET /api/finance/personal/budgets/{id}/progress/
```

**Response:**
```json
{
  "budget_id": 1,
  "name": "Monthly Food Budget",
  "allocated_amount": "800.00",
  "spent_amount": "650.00",
  "remaining_amount": "150.00",
  "progress_percentage": 81.25,
  "is_exceeded": false,
  "period": "monthly",
  "start_date": "2024-01-01",
  "end_date": "2024-01-31"
}
```

#### Current Budgets
```
GET /api/finance/personal/budgets/current_budgets/
```

### Personal Savings Goals

#### List Savings Goals
```
GET /api/finance/personal/savings-goals/
```

#### Create Savings Goal
```
POST /api/finance/personal/savings-goals/
```

**Request Body:**
```json
{
  "name": "Emergency Fund",
  "target_amount": "10000.00",
  "current_amount": "2500.00",
  "target_date": "2024-12-31",
  "description": "Build emergency fund for 6 months expenses"
}
```

#### Goal Progress
```
GET /api/finance/personal/savings-goals/{id}/progress/
```

#### Add Contribution
```
POST /api/finance/personal/savings-goals/{id}/add_contribution/
```

**Request Body:**
```json
{
  "amount": "500.00"
}
```

### Recurring Transactions

#### List Recurring Transactions
```
GET /api/finance/personal/recurring-transactions/
```

#### Create Recurring Transaction
```
POST /api/finance/personal/recurring-transactions/
```

**Request Body:**
```json
{
  "name": "Monthly Salary",
  "type": "income",
  "amount": "2500.00",
  "account": 1,
  "description": "Monthly salary payment",
  "income_source": "salary",
  "reason": "Regular monthly income",
  "frequency": "monthly",
  "next_due_date": "2024-02-01"
}
```

#### Execute Recurring Transaction
```
POST /api/finance/personal/recurring-transactions/{id}/execute_now/
```

#### Due Today
```
GET /api/finance/personal/recurring-transactions/due_today/
```

### Dashboard

#### Personal Finance Dashboard
```
GET /api/finance/personal/dashboard/
```

**Response:**
```json
{
  "total_balance": "8500.00",
  "accounts_count": 3,
  "monthly_income": "3000.00",
  "monthly_expenses": "1800.00",
  "monthly_expenses_excluding_charges": "1750.00",
  "monthly_transaction_charges": "50.00",
  "net_monthly": "1200.00",
  "active_budgets": 5,
  "active_savings_goals": 2,
  "due_recurring_transactions": 1,
  "transactions_this_month": 28
}
```

## Error Responses

### Standard Error Format
```json
{
  "error": "Error message",
  "details": "Additional error details"
}
```

### Common HTTP Status Codes
- `200 OK`: Successful request
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

## Usage Examples

### Creating a Complete Personal Finance Setup

1. **Create Personal Accounts:**
```bash
# Bank Account
curl -X POST /api/finance/personal/accounts/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Main Bank Account",
    "type": "bank",
    "currency": "UGX",
    "balance": "5000.00"
  }'

# Mobile Money Account
curl -X POST /api/finance/personal/accounts/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MTN Mobile Money",
    "type": "mobile_money",
    "currency": "UGX",
    "balance": "500.00"
  }'
```

2. **Set Up Budgets:**
```bash
curl -X POST /api/finance/personal/budgets/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Monthly Food Budget",
    "category": "food",
    "allocated_amount": "800.00",
    "period": "monthly",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }'
```

3. **Create Savings Goals:**
```bash
curl -X POST /api/finance/personal/savings-goals/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Emergency Fund",
    "target_amount": "10000.00",
    "current_amount": "0.00",
    "target_date": "2024-12-31"
  }'
```

4. **Set Up Recurring Transactions:**
```bash
curl -X POST /api/finance/personal/recurring-transactions/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Monthly Salary",
    "type": "income",
    "amount": "2500.00",
    "account": 1,
    "description": "Monthly salary payment",
    "income_source": "salary",
    "frequency": "monthly"
  }'
```

5. **Record Transactions:**
```bash
curl -X POST /api/finance/personal/transactions/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "expense",
    "amount": "150.00",
    "account": 1,
    "description": "Grocery shopping",
    "expense_category": "food",
    "reason": "Weekly groceries",
    "tags": ["groceries", "food"]
  }'
```

## Integration Notes

### Frontend Integration
- Use the dashboard endpoint for overview widgets
- Implement real-time balance updates after transactions
- Show budget progress bars and savings goal progress
- Display due recurring transactions as notifications

### Mobile App Integration
- Support offline transaction recording with sync
- Implement receipt image capture and upload
- Use location services for automatic location tagging
- Push notifications for budget alerts and due recurring transactions

### Reporting Integration
- Monthly summary data for financial reports
- Category breakdown for spending analysis
- Export capabilities for external analysis tools
- Integration with tax preparation software

## Recent Updates & Bug Fixes

### January 2024 - Version 1.0
- ✅ Fixed field name inconsistencies across models and serializers
- ✅ Updated `transaction_type` to `type` in PersonalTransactionRecurring model
- ✅ Changed `budgeted_amount` to `allocated_amount` in PersonalBudget model
- ✅ Updated `title` to `name` in PersonalSavingsGoal model
- ✅ Fixed `next_execution_date` to `next_due_date` for recurring transactions
- ✅ Corrected property names: `spent_percentage` → `progress_percentage`, `is_over_budget` → `is_exceeded`
- ✅ Added missing analytics serializers for dashboard endpoints
- ✅ Fixed admin interface field references
- ✅ Resolved all Django system check errors
- ✅ Fixed min_value warning in serializers (now uses Decimal instances)

## Security Considerations

- All endpoints require user authentication
- Users can only access their own financial data
- Sensitive financial data is encrypted at rest
- API rate limiting is implemented
- Audit logging for all financial operations

## Performance Optimization

- Database indexes on frequently queried fields
- Pagination for large result sets
- Caching for dashboard and summary data
- Optimized queries with select_related and prefetch_related
- Background tasks for recurring transaction processing

## Development Status

### ✅ Completed Features
- Personal account management with multiple account types
- Transaction recording with detailed categorization
- Budget tracking with progress monitoring
- Savings goals with contribution tracking
- Recurring transaction templates and automation
- Analytics and insights generation
- Dashboard overview with key metrics
- Admin interface for testing and management

### 🔧 Technical Implementation
- All models properly defined with correct field names
- Serializers with proper validation and field mapping
- ViewSets with custom actions for analytics
- Service layer for business logic
- URL routing configured
- Admin interface fully functional
- No system check errors or warnings

### 📊 API Endpoints Status
- ✅ Personal Accounts: Full CRUD operations
- ✅ Personal Transactions: CRUD + analytics actions
- ✅ Personal Budgets: CRUD + progress tracking
- ✅ Personal Savings Goals: CRUD + contribution management
- ✅ Recurring Transactions: CRUD + execution management
- ✅ Dashboard: Overview data aggregation

The personal finance system is production-ready and fully tested.
