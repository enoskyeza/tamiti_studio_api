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
    PERSONAL_BANK = 'personal_bank', 'Personal Bank Account'
    AIRTEL_MONEY = 'airtel_money', 'Airtel Money'
    MTN_MONEY = 'mtn_money', 'MTN Mobile Money'
    CASH_WALLET = 'cash_wallet', 'Cash Wallet'
    SAVINGS_ACCOUNT = 'savings_account', 'Savings Account'
    CREDIT_CARD = 'credit_card', 'Credit Card'


class Currency(BaseEnum):
    Uganda = 'UGX', 'UGX'
    USD = 'USD', 'USD'
    EUR = 'EUR', 'EUR'
    KES = 'KES', 'KES'


class PriorityLevel(BaseEnum):
    LOW = 'low', 'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH = 'high', 'High'
    URGENT = 'urgent', 'Urgent'


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
    INVOICE = 'invoice', 'Invoice Payment'
    MISC = 'miscellaneous', 'Miscellaneous'
    SACCO_SAVINGS = 'sacco_savings', 'SACCO Savings'
    SACCO_LOAN_DISBURSEMENT = 'sacco_loan_disbursement', 'SACCO Loan Disbursement'
    SACCO_LOAN_REPAYMENT = 'sacco_loan_repayment', 'SACCO Loan Repayment'
    SACCO_WELFARE = 'sacco_welfare', 'SACCO Welfare'
    SACCO_DEVELOPMENT = 'sacco_development', 'SACCO Development'
    SACCO_EMERGENCY = 'sacco_emergency', 'SACCO Emergency Support'
    SACCO_WITHDRAWAL = 'sacco_withdrawal', 'SACCO Withdrawal'


class TaskStatus(BaseEnum):
    TODO = 'todo', 'To Do'
    IN_PROGRESS = 'in_progress', 'In Progress'
    REVIEW = 'review', 'Review'
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
    FINANCE = 'finance', 'Finance'
    FIELD = 'field', 'Field'


class EnergyLevel(BaseEnum):
    LOW = 'low', 'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH = 'high', 'High'


class BlockStatus(BaseEnum):
    PLANNED = 'planned', 'Planned'
    COMMITTED = 'committed', 'Committed'
    IN_PROGRESS = 'in_progress', 'In Progress'
    DONE = 'done', 'Done'
    SKIPPED = 'skipped', 'Skipped'


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


class ChannelType(BaseEnum):
    PUBLIC = 'public', 'Public'
    PRIVATE = 'private', 'Private'
    DIRECT = 'direct', 'Direct Message'


class SocialPlatformType(BaseEnum):
    FACEBOOK = "facebook", "Facebook"
    INSTAGRAM = "instagram", "Instagram"
    X = "x", "X (formerly Twitter)"
    LINKEDIN = "linkedin", "LinkedIn"
    TIKTOK = "tiktok", "TikTok"
    YOUTUBE = "youtube", "YouTube"


class PostStatus(BaseEnum):
    DRAFT = "draft", "Draft"
    UNDER_REVIEW = "under_review", "Under Review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    PUBLISHED = "published", "Published"


class AssetType(BaseEnum):
    PHOTO = "photo", "Photo"
    VIDEO = "video", "Video"
    DOCUMENT = "document", "Document"
    OTHER = "other", "Other"


class QuotationStatus(BaseEnum):
    DRAFT = 'draft', 'Draft'
    SENT = 'sent', 'Sent'
    ACCEPTED = 'accepted', 'Accepted'
    REJECTED = 'rejected', 'Rejected'
    EXPIRED = 'expired', 'Expired'


class PaymentMethod(BaseEnum):
    CASH = 'cash', 'Cash'
    BANK_TRANSFER = 'bank_transfer', 'Bank Transfer'
    MOBILE_MONEY = 'mobile_money', 'Mobile Money'
    CARD = 'card', 'Card'
    CHEQUE = 'cheque', 'Cheque'
    OTHER = 'other', 'Other'


class FinanceScope(BaseEnum):
    COMPANY = 'company', 'Company'
    PERSONAL = 'personal', 'Personal'
    SACCO = 'sacco', 'SACCO'


class PersonalExpenseCategory(BaseEnum):
    FOOD = 'food', 'Food & Dining'
    TRANSPORT = 'transport', 'Transportation'
    UTILITIES = 'utilities', 'Utilities'
    ENTERTAINMENT = 'entertainment', 'Entertainment'
    HEALTHCARE = 'healthcare', 'Healthcare'
    SHOPPING = 'shopping', 'Shopping'
    EDUCATION = 'education', 'Education'
    SAVINGS = 'savings', 'Savings & Investment'
    DEBT = 'debt', 'Debt Payment'
    RENT = 'rent', 'Rent & Housing'
    INSURANCE = 'insurance', 'Insurance'
    SUBSCRIPTIONS = 'subscriptions', 'Subscriptions'
    GIFTS = 'gifts', 'Gifts & Donations'
    TRANSFER = 'transfer', 'Account Transfer'
    TRANSFER_FEE = 'transfer_fee', 'Transfer Fee'
    LOAN_GIVEN = 'loan_given', 'Loan Given'
    DEBT_INTEREST = 'debt_interest', 'Debt Interest'
    OTHER = 'other', 'Other'
    DONATION = 'donation', 'Donations/Gifts'
    OWNER_DRAW = 'owner_draw', 'Owner Draw'


class PersonalIncomeSource(BaseEnum):
    SALARY = 'salary', 'Salary'
    FREELANCE = 'freelance', 'Freelance Work'
    BUSINESS = 'business', 'Business Income'
    INVESTMENT = 'investment', 'Investment Returns'
    RENTAL = 'rental', 'Rental Income'
    GIFT = 'gift', 'Gift/Allowance'
    REFUND = 'refund', 'Refund'
    BONUS = 'bonus', 'Bonus'
    TRANSFER = 'transfer', 'Account Transfer'
    LOAN_REPAYMENT = 'loan_repayment', 'Loan Repayment'
    LOAN_INTEREST = 'loan_interest', 'Loan Interest'
    DONATION = 'donation', 'Donation'
    SPONSORSHIP = 'sponsorship', 'Sponsorship'
    OWNER_CONTRIBUTION = 'owner_contribution', 'Owner Contribution'
    OTHER = 'other', 'Other'


class BudgetPeriod(BaseEnum):
    WEEKLY = 'weekly', 'Weekly'
    MONTHLY = 'monthly', 'Monthly'
    QUARTERLY = 'quarterly', 'Quarterly'
    YEARLY = 'yearly', 'Yearly'
