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
