# Finance App - Complete API Documentation

## Overview

The Finance app provides comprehensive financial management capabilities for both company and personal finances. It includes invoice management, payment tracking, budgeting, savings goals, debt management, and financial analytics.

## Core Models and Data Structures

### 1. Party Model
**Purpose**: Represents customers, suppliers, and other business entities

**Fields**:
- `name` (CharField, max_length=255) - Party name
- `email` (EmailField, optional) - Contact email
- `phone` (CharField, max_length=20, optional) - Contact phone
- `address` (TextField, optional) - Physical address
- `tax_number` (CharField, max_length=50, optional) - Tax identification
- `created_at` (DateTimeField, auto_now_add=True)
- `updated_at` (DateTimeField, auto_now=True)

### 2. Account Model
**Purpose**: Financial accounts for both company and personal use

**Fields**:
- `name` (CharField, max_length=255) - Account name
- `number` (CharField, max_length=50, optional) - Account number
- `type` (CharField, choices=ACCOUNT_TYPES) - bank, cash, mobile_money, etc.
- `currency` (CharField, max_length=3, default='UGX')
- `balance` (DecimalField, max_digits=12, decimal_places=2, default=0)
- `scope` (CharField, choices=FinanceScope) - PERSONAL or COMPANY
- `owner` (ForeignKey to User, optional) - For personal accounts
- `is_active` (BooleanField, default=True)
- `created_at` (DateTimeField, auto_now_add=True)

**Properties**:
- `balance` - Calculated from related transactions

### 3. Invoice Model
**Purpose**: Manages invoices for sales and purchases

**Fields**:
- `number` (CharField, max_length=100, unique=True) - Invoice number
- `party` (ForeignKey to Party) - Customer/supplier
- `direction` (CharField, choices=InvoiceDirection) - INCOMING/OUTGOING
- `total` (DecimalField, max_digits=12, decimal_places=2)
- `issue_date` (DateField) - Invoice date
- `due_date` (DateField) - Payment due date
- `notes` (TextField, optional)
- `attachment` (FileField, optional)
- `created_by` (ForeignKey to User)
- `created_at` (DateTimeField, auto_now_add=True)

**Properties**:
- `amount_paid` - Total payments received
- `amount_due` - Outstanding amount
- `is_paid` - Boolean payment status

## API Endpoints

### Company Finance Endpoints

#### 1. Parties Management
**Base URL**: `/api/finance/parties/`

**GET /api/finance/parties/**
- **Purpose**: List all parties
- **Response**:
```json
{
  "count": 25,
  "results": [
    {
      "id": 1,
      "name": "ABC Company Ltd",
      "email": "contact@abc.com",
      "phone": "+256700123456",
      "address": "Kampala, Uganda",
      "tax_number": "1234567890",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

**POST /api/finance/parties/**
- **Purpose**: Create new party
- **Request**:
```json
{
  "name": "XYZ Suppliers",
  "email": "info@xyz.com",
  "phone": "+256701234567",
  "address": "Entebbe, Uganda",
  "tax_number": "0987654321"
}
```

#### 2. Accounts Management
**Base URL**: `/api/finance/accounts/`

**GET /api/finance/accounts/**
- **Purpose**: List accessible accounts (filtered by permissions)
- **Response**:
```json
{
  "count": 5,
  "results": [
    {
      "id": 1,
      "name": "Main Business Account",
      "number": "1234567890",
      "type": "bank",
      "currency": "UGX",
      "balance": "5000000.00",
      "scope": "company",
      "is_active": true,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### 3. Invoices Management
**Base URL**: `/api/finance/invoices/`

**GET /api/finance/invoices/**
- **Purpose**: List all invoices
- **Query Parameters**: `direction`, `party`, `issue_date`, `due_date`, `number`
- **Response**:
```json
{
  "count": 50,
  "results": [
    {
      "id": 1,
      "number": "INV-2024-001",
      "party": {
        "id": 1,
        "name": "ABC Company Ltd"
      },
      "direction": "outgoing",
      "total": "1500000.00",
      "amount_paid": "500000.00",
      "amount_due": "1000000.00",
      "issue_date": "2024-01-15",
      "due_date": "2024-02-15",
      "is_paid": false
    }
  ]
}
```

**POST /api/finance/invoices/**
- **Purpose**: Create new invoice
- **Request**:
```json
{
  "party": 1,
  "direction": "outgoing",
  "total": "2000000.00",
  "issue_date": "2024-01-20",
  "due_date": "2024-02-20",
  "notes": "Payment terms: 30 days"
}
```

**POST /api/finance/invoices/{id}/pay/**
- **Purpose**: Record payment for invoice
- **Request**:
```json
{
  "amount": "500000.00",
  "account": 1,
  "method": "bank_transfer",
  "notes": "Partial payment"
}
```

#### 4. Transactions Management
**Base URL**: `/api/finance/transactions/`

**GET /api/finance/transactions/**
- **Purpose**: List transactions (filtered by account access)
- **Response**:
```json
{
  "count": 100,
  "results": [
    {
      "id": 1,
      "account": {
        "id": 1,
        "name": "Main Business Account"
      },
      "type": "income",
      "amount": "500000.00",
      "description": "Invoice payment received",
      "date": "2024-01-20",
      "reference_number": "TXN-001"
    }
  ]
}
```

#### 5. Debt Management
**Base URL**: `/api/finance/debts/`

**GET /api/finance/debts/debtors/**
- **Purpose**: Get parties who owe money (AR)
- **Response**:
```json
[
  {
    "party_id": 1,
    "party_name": "ABC Company Ltd",
    "party_email": "contact@abc.com",
    "invoice_count": 3,
    "total_invoiced": "3000000.00",
    "total_paid": "1000000.00",
    "total_outstanding": "2000000.00"
  }
]
```

**GET /api/finance/debts/creditors/**
- **Purpose**: Get parties we owe money (AP)

### Personal Finance Endpoints

#### 1. Personal Accounts
**Base URL**: `/api/finance/personal/accounts/`

**GET /api/finance/personal/accounts/**
- **Purpose**: List user's personal accounts
- **Response**:
```json
{
  "count": 3,
  "results": [
    {
      "id": 10,
      "name": "Personal Savings",
      "number": "9876543210",
      "type": "bank",
      "currency": "UGX",
      "balance": "2500000.00",
      "is_active": true
    }
  ]
}
```

**POST /api/finance/personal/accounts/**
- **Request**:
```json
{
  "name": "Emergency Fund",
  "type": "bank",
  "currency": "UGX",
  "number": "1122334455"
}
```

#### 2. Personal Transactions
**Base URL**: `/api/finance/personal/transactions/`

**GET /api/finance/personal/transactions/**
- **Purpose**: List user's personal transactions
- **Response**:
```json
{
  "count": 200,
  "results": [
    {
      "id": 1,
      "type": "expense",
      "amount": "50000.00",
      "account": {
        "id": 10,
        "name": "Personal Savings"
      },
      "description": "Grocery shopping",
      "expense_category": "food",
      "date": "2024-01-20",
      "transaction_charge": "1000.00"
    }
  ]
}
```

**POST /api/finance/personal/transactions/**
- **Request**:
```json
{
  "type": "expense",
  "amount": "75000.00",
  "account": 10,
  "description": "Fuel for car",
  "expense_category": "transport",
  "transaction_charge": "2000.00"
}
```

**GET /api/finance/personal/transactions/monthly_summary/**
- **Purpose**: Get monthly income/expense summary
- **Query Parameters**: `year`, `month`
- **Response**:
```json
{
  "year": 2024,
  "month": 1,
  "total_income": "3000000.00",
  "total_expenses": "1500000.00",
  "net_amount": "1500000.00",
  "transaction_count": 45,
  "income_by_source": {
    "salary": "2500000.00",
    "freelance": "500000.00"
  },
  "expenses_by_category": {
    "food": "400000.00",
    "transport": "300000.00",
    "utilities": "200000.00"
  }
}
```

#### 3. Personal Budgets
**Base URL**: `/api/finance/personal/budgets/`

**GET /api/finance/personal/budgets/**
- **Response**:
```json
{
  "count": 5,
  "results": [
    {
      "id": 1,
      "name": "Monthly Food Budget",
      "category": "food",
      "allocated_amount": "500000.00",
      "spent_amount": "350000.00",
      "remaining_amount": "150000.00",
      "progress_percentage": 70.0,
      "period": "monthly",
      "start_date": "2024-01-01",
      "end_date": "2024-01-31",
      "is_active": true
    }
  ]
}
```

**GET /api/finance/personal/budgets/{id}/progress/**
- **Response**:
```json
{
  "budget_id": 1,
  "name": "Monthly Food Budget",
  "allocated_amount": "500000.00",
  "spent_amount": "350000.00",
  "remaining_amount": "150000.00",
  "progress_percentage": 70.0,
  "is_exceeded": false
}
```

#### 4. Savings Goals
**Base URL**: `/api/finance/personal/savings-goals/`

**GET /api/finance/personal/savings-goals/**
- **Response**:
```json
{
  "count": 3,
  "results": [
    {
      "id": 1,
      "name": "Emergency Fund",
      "target_amount": "5000000.00",
      "current_amount": "2500000.00",
      "remaining_amount": "2500000.00",
      "progress_percentage": 50.0,
      "target_date": "2024-12-31",
      "is_achieved": false
    }
  ]
}
```

**POST /api/finance/personal/savings-goals/{id}/add_contribution/**
- **Request**:
```json
{
  "amount": "100000.00"
}
```
- **Response**:
```json
{
  "message": "Contribution added successfully",
  "new_current_amount": "2600000.00",
  "progress_percentage": 52.0,
  "is_achieved": false
}
```

#### 5. Debt Management
**Base URL**: `/api/finance/personal/debts/`

**GET /api/finance/personal/debts/**
- **Response**:
```json
{
  "count": 2,
  "results": [
    {
      "id": 1,
      "creditor_name": "Bank Loan",
      "amount_borrowed": "10000000.00",
      "amount_paid": "3000000.00",
      "balance": "7000000.00",
      "borrowed_date": "2023-06-01",
      "due_date": "2025-06-01",
      "interest_rate": "15.00",
      "description": "Car loan"
    }
  ]
}
```

**POST /api/finance/personal/debts/{id}/make_payment/**
- **Request**:
```json
{
  "amount": "500000.00",
  "payment_date": "2024-01-20",
  "notes": "Monthly payment"
}
```

#### 6. Dashboard and Analytics
**GET /api/finance/personal/dashboard/**
- **Purpose**: Personal finance overview
- **Response**:
```json
{
  "total_balance": "5500000.00",
  "accounts_count": 3,
  "monthly_income": "3000000.00",
  "monthly_expenses": "1500000.00",
  "net_monthly": "1500000.00",
  "active_budgets": 5,
  "active_savings_goals": 3,
  "due_recurring_transactions": 2,
  "transactions_this_month": 45
}
```

## Data Validation Rules

### Account Validation
- Name is required and max 255 characters
- Account number is optional but must be unique if provided
- Balance cannot be negative for certain account types
- Personal accounts must have an owner

### Invoice Validation
- Invoice number must be unique
- Total amount must be positive
- Due date must be after issue date
- Direction must be 'incoming' or 'outgoing'

### Transaction Validation
- Amount must be positive
- Date cannot be in the future
- Account must exist and be active
- Type must be 'income' or 'expense'

### Personal Finance Validation
- Budget allocated amount must be positive
- Savings goal target amount must be positive
- Debt amounts must be positive
- Due dates must be after borrowed/start dates

## Permission System Integration

### Account Access Control
- Personal accounts: Only visible to owner
- Company accounts: Based on permission system
- If no permissions defined, defaults to full access (backward compatibility)

### Transaction Filtering
- Users only see transactions for accounts they have access to
- Filtering applied at queryset level for performance

## Error Handling

### Common Error Responses
```json
{
  "error": "Validation failed",
  "details": {
    "amount": ["This field must be a positive number"],
    "due_date": ["Due date must be after issue date"]
  }
}
```

### HTTP Status Codes
- 200: Success
- 201: Created
- 400: Bad Request (validation errors)
- 401: Unauthorized
- 403: Forbidden (permission denied)
- 404: Not Found
- 500: Internal Server Error

## Performance Considerations

### Query Optimization
- Uses select_related() for foreign key relationships
- Prefetch_related() for reverse foreign keys
- Database indexes on frequently queried fields
- Pagination for large result sets

### Caching
- Permission checks use caching for performance
- Account balances calculated on-demand with caching

## Security Features

### Authentication
- All endpoints require authentication
- JWT token-based authentication

### Authorization
- Permission-based access control for company resources
- User-scoped access for personal resources
- Object-level permissions where applicable

### Data Protection
- Sensitive financial data encrypted at rest
- Audit logging for financial transactions
- Input validation and sanitization
