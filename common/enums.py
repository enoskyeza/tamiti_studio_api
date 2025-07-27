from django.db import models


class BaseEnum(models.TextChoices):
    @classmethod
    def choices(cls):
        return [(choice.value, choice.label) for choice in cls]


class PartyType(BaseEnum):
    CLIENT = 'client', 'Client'
    VENDOR = 'vendor', 'Vendor'
    DONOR = 'donor', 'Donor'
    INVESTOR = 'investor', 'Investor'
    PARTNER = 'partner', 'Partner'
    INTERNAL = 'internal', 'Internal'


class InvoiceDirection(BaseEnum):
    INCOMING = 'incoming', 'Incoming'
    OUTGOING = 'outgoing', 'Outgoing'


class TransactionType(BaseEnum):
    INCOME = 'income', 'Income'
    EXPENSE = 'expense', 'Expense'


class AccountType(BaseEnum):
    BANK = 'bank', 'Bank'
    MOBILE_MONEY = 'mobile_money', 'Mobile Money'
    WALLET = 'wallet', 'Wallet'
    PAYPAL = 'paypal', 'Paypal'
    CASHBOX = 'cashbox', 'Cashbox'


class Currency(BaseEnum):
    Uganda = 'UGX', 'UGX'
    USD = 'USD', 'USD'
    EUR = 'EUR', 'EUR'
    KES = 'KES', 'KES'


class PriorityLevel(BaseEnum):
    LOW = 'low', 'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH = 'high', 'High'
    CRITICAL = 'critical', 'Critical'


class PaymentCategory(BaseEnum):
    WEB_DEV = 'web_dev', 'Web Development'
    APP_DEV = 'app_dev', 'App Development'
    TRAINING = 'training', 'Training'
    FACILITATION = 'facilitation', 'Facilitation'
    TRAVEL = 'travel', 'Travel'
    MARKETING = 'marketing', 'Marketing'
    SALARY = 'salary', 'Salary'
    INFRASTRUCTURE = 'infrastructure', 'Infrastructure'
    OPERATIONS = 'operations', 'Operations'
    UTILITIES = 'utilities', 'Utilities'
    OFFICE = 'office', 'Office Supplies'
    TAX = 'tax', 'Tax'
    MISC = 'miscellaneous', 'Miscellaneous'


class TaskStatus(BaseEnum):
    TODO = 'todo', 'To Do'
    IN_PROGRESS = 'in_progress', 'In Progress'
    DONE = 'done', 'Done'


class ProjectStatus(BaseEnum):
    PLANNING = 'planning', 'Planning'
    ACTIVE = 'active', 'Active'
    PAUSED = 'paused', 'Paused'
    REVIEW = 'review', 'Review'
    COMPLETE = 'complete', 'Complete'
    CANCELLED = 'cancelled', 'Cancelled'
    ARCHIVED = 'archived', 'Archived'


class ProjectRole(BaseEnum):
    OWNER = 'owner', 'Owner'
    MANAGER = 'manager', 'Manager'
    CONTRIBUTOR = 'contributor', 'Contributor'
    VIEWER = 'viewer', 'Viewer'


class OriginApp(BaseEnum):
    TASKS = 'tasks', 'Tasks'
    PROJECTS = 'projects', 'Projects'
    DIGITAL = 'digital', 'Digital'
    LEADS = 'leads', 'Leads'


class LeadStatus(BaseEnum):
    NEW = 'new', 'New'
    INTERESTED = 'interested', 'Interested'
    FOLLOW_UP = 'follow_up', 'Follow-up Scheduled'
    QUOTE_SENT = 'quote_sent', 'Quote Sent'
    CLOSED_SUBSCRIBED = 'closed_subscribed', 'Closed – Subscribed'
    CLOSED_LOST = 'closed_lost', 'Closed – Lost'
    ON_HOLD = 'on_hold', 'On Hold'


class VisitOutcome(BaseEnum):
    NO_ANSWER = 'no_answer', 'No Answer'
    REFUSAL = 'refusal', 'Refusal'
    INTERESTED = 'interested', 'Interested'
    COMPLETED = 'completed', 'GPB Setup Completed'
    SALE_CLOSED = 'sale_closed', 'Sale Closed'
    OTHER = 'other', 'Other'


class FollowUpType(BaseEnum):
    CALL = 'call', 'Call'
    DEMO = 'demo', 'Demo'
    MEETING = 'meeting', 'Meeting'
    INSTALL = 'install', 'Install'
    CHECKIN = 'checkin', 'Check-In'


class LeadStage(BaseEnum):
    PROSPECT = 'prospect', 'Prospect'
    QUALIFIED = 'qualified', 'Qualified'
    NEGOTIATION = 'negotiation', 'Negotiation'
    WON = 'won', 'Won'
    LOST = 'lost', 'Lost'


class LeadSource(BaseEnum):
    FIELD = 'field', 'Field Visit'
    REFERRAL = 'referral', 'Referral'
    DIGITAL = 'digital', 'Digital'
    INBOUND = 'inbound', 'Inbound'
    OTHER = 'other', 'Other'

