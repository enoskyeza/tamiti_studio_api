# tests/factories.py
from django.utils import timezone
from datetime import timezone as dt_timezone

import factory

from users.models import User
from factory.django import DjangoModelFactory
from projects.models import Project, Milestone
from comments.models import Comment
from django.contrib.contenttypes.models import ContentType
from tasks.models import Task, TaskGroup
from field.models import Zone, Lead, Visit, LeadAction
from common.enums import *
from social.models import SocialPost, PostComment, SocialMetric, SocialPlatformProfile
from finance.models import (
    Party, Account, Invoice, Payment, Transaction, Goal, GoalMilestone, Requisition
)
from chatrooms.models import (
    Channel, ChannelMessage, ChannelMember,
    DirectThread, DirectMessage
)
from ticketing.models import (
    Event, EventMembership, BatchMembership, TicketType, Batch, Ticket, ScanLog
)


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')
    is_verified = True


class ProjectFactory(DjangoModelFactory):
    class Meta:
        model = Project

    name = factory.Sequence(lambda n: f"Project {n}")
    description = "Test project"
    client_name = "Client Inc."
    status = ProjectStatus.PLANNING
    priority = PriorityLevel.MEDIUM
    start_date = factory.Faker("date_this_year")
    due_date = factory.Faker("date_this_year")
    created_by = factory.SubFactory(UserFactory)


class MilestoneFactory(DjangoModelFactory):
    class Meta:
        model = Milestone

    project = factory.SubFactory(ProjectFactory)
    name = factory.Sequence(lambda n: f"Milestone {n}")
    due_date = factory.Faker("date_this_year")


class TaskFactory(DjangoModelFactory):
    class Meta:
        model = Task

    project = factory.SubFactory(ProjectFactory)
    title = factory.Sequence(lambda n: f"Task {n}")
    description = "A test task"
    priority = PriorityLevel.MEDIUM
    due_date = factory.Faker("future_datetime")
    created_by = factory.SubFactory(UserFactory)


class TaskGroupFactory(DjangoModelFactory):
    class Meta:
        model = TaskGroup

    project = factory.SubFactory(ProjectFactory)
    name = factory.Sequence(lambda n: f"Group {n}")


class ProjectCommentFactory(DjangoModelFactory):
    class Meta:
        model = Comment

    author = factory.SubFactory(UserFactory)
    content = "This is a comment"
    is_internal = True
    content_type = factory.LazyAttribute(lambda obj: ContentType.objects.get_for_model(Project))
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # Handle project parameter
        project = kwargs.pop('project', None)
        if not project:
            project = ProjectFactory()
        
        kwargs['object_id'] = project.id
        return super()._create(model_class, *args, **kwargs)


class PartyFactory(DjangoModelFactory):
    class Meta:
        model = Party

    name = factory.Faker('company')
    email = factory.Faker('email')
    phone = factory.Faker('phone_number')
    type = PartyType.CLIENT


class AccountFactory(DjangoModelFactory):
    class Meta:
        model = Account

    name = factory.Faker('company')
    number = factory.Faker('iban')
    type = AccountType.BANK
    balance = 0
    currency = Currency.UGX


class InvoiceFactory(DjangoModelFactory):
    class Meta:
        model = Invoice

    party = factory.SubFactory(PartyFactory)
    direction = InvoiceDirection.OUTGOING
    total = 500000
    issue_date = factory.LazyFunction(lambda: timezone.now().date())
    due_date = factory.LazyFunction(lambda: timezone.now().date())


class RequisitionFactory(DjangoModelFactory):
    class Meta:
        model = Requisition

    requested_by = factory.SubFactory(UserFactory)
    approved_by = factory.SubFactory(UserFactory)
    urgency = PriorityLevel.MEDIUM
    status = 'approved'
    amount = 200000
    purpose = factory.Faker('sentence')
    comments = ''


class GoalFactory(DjangoModelFactory):
    class Meta:
        model = Goal

    title = factory.Faker('sentence')
    target_amount = 1000000
    current_amount = 0
    due_date = factory.LazyFunction(lambda: timezone.now().date())
    owner = factory.SubFactory(UserFactory)


class GoalMilestoneFactory(DjangoModelFactory):
    class Meta:
        model = GoalMilestone

    goal = factory.SubFactory(GoalFactory)
    amount = 250000


class TransactionFactory(DjangoModelFactory):
    class Meta:
        model = Transaction

    type = TransactionType.EXPENSE
    amount = 100000
    account = factory.SubFactory(AccountFactory)
    date = factory.LazyFunction(timezone.now)
    is_automated = True


class PaymentFactory(DjangoModelFactory):
    class Meta:
        model = Payment

    direction = 'outgoing'
    amount = 100000
    party = factory.SubFactory(PartyFactory)
    invoice = factory.SubFactory(InvoiceFactory)
    requisition = factory.SubFactory(RequisitionFactory)
    account = factory.SubFactory(AccountFactory)
    goal = factory.SubFactory(GoalFactory)
    notes = factory.Faker('sentence')

class ZoneFactory(DjangoModelFactory):
    class Meta:
        model = Zone

    name = factory.Sequence(lambda n: f'Zone {n}')
    region = "Central"
    created_by = factory.SubFactory(UserFactory)


class LeadFactory(DjangoModelFactory):
    class Meta:
        model = Lead

    business_name = factory.Sequence(lambda n: f'Biz {n}')
    contact_name = "John Doe"
    contact_phone = "0770000000"
    contact_email = factory.LazyAttribute(lambda o: f"{o.business_name.lower().replace(' ', '')}@example.com")
    stage = LeadStage.PROSPECT
    source = LeadSource.FIELD
    zone = factory.SubFactory(ZoneFactory)
    assigned_rep = factory.SubFactory(UserFactory)
    priority = PriorityLevel.MEDIUM
    products_discussed = ["Website", "App"]


class VisitFactory(DjangoModelFactory):
    class Meta:
        model = Visit

    rep = factory.SubFactory(UserFactory)
    zone = factory.SubFactory(ZoneFactory)
    date_time = factory.LazyFunction(timezone.now)
    business_name = factory.Sequence(lambda n: f'BizVisit {n}')
    contact_name = "Jane Contact"
    contact_phone = "0788888888"
    products_discussed = ["Hosting", "Training"]
    location = "Kampala"
    add_as_lead = True


class LeadActionFactory(DjangoModelFactory):
    class Meta:
        model = LeadAction

    lead = factory.SubFactory(LeadFactory)
    type = FollowUpType.CALL
    date = factory.LazyFunction(timezone.now)
    created_by = factory.SubFactory(UserFactory)
    outcome = "Reached out"


class ChannelFactory(DjangoModelFactory):
    class Meta:
        model = Channel

    name = factory.Sequence(lambda n: f"channel-{n}")
    type = "public"
    is_private = False
    created_by = factory.SubFactory(UserFactory)


class ChannelMemberFactory(DjangoModelFactory):
    class Meta:
        model = ChannelMember

    channel = factory.SubFactory(ChannelFactory)
    user = factory.SubFactory(UserFactory)


class ChannelMessageFactory(DjangoModelFactory):
    class Meta:
        model = ChannelMessage

    channel = factory.SubFactory(ChannelFactory)
    sender = factory.SubFactory(UserFactory)
    content = factory.Faker("sentence")
    timestamp = factory.LazyFunction(timezone.now)


class DirectThreadFactory(DjangoModelFactory):
    class Meta:
        model = DirectThread

    user_1 = factory.SubFactory(UserFactory)
    user_2 = factory.SubFactory(UserFactory)


class DirectMessageFactory(DjangoModelFactory):
    class Meta:
        model = DirectMessage

    thread = factory.SubFactory(DirectThreadFactory)
    sender = factory.SubFactory(UserFactory)
    content = factory.Faker("sentence")
    timestamp = factory.LazyFunction(timezone.now)


class SocialPostFactory(DjangoModelFactory):
    class Meta:
        model = SocialPost

    title = factory.Faker("sentence")
    content_text = factory.Faker("paragraph")
    platform = "facebook"
    scheduled_for = factory.LazyFunction(timezone.now)
    status = "draft"
    assigned_to = factory.SubFactory(UserFactory)


class PostCommentFactory(DjangoModelFactory):
    class Meta:
        model = PostComment

    post = factory.SubFactory(SocialPostFactory)
    author = factory.SubFactory(UserFactory)
    content = factory.Faker("sentence")


class SocialMetricFactory(DjangoModelFactory):
    class Meta:
        model = SocialMetric

    post = factory.SubFactory(SocialPostFactory)
    likes = 10
    shares = 5
    comments = 3
    views = 100


class SocialPlatformProfileFactory(DjangoModelFactory):
    class Meta:
        model = SocialPlatformProfile

    platform = "facebook"
    followers = 1000
    posts_made = 20


# Ticketing Factories
class EventFactory(DjangoModelFactory):
    class Meta:
        model = Event

    name = factory.Sequence(lambda n: f"Event {n}")
    description = factory.Faker("paragraph")
    date = factory.Faker("future_datetime", tzinfo=dt_timezone.utc)
    venue = factory.Faker("city")
    status = "active"
    created_by = factory.SubFactory(UserFactory)


class EventMembershipFactory(DjangoModelFactory):
    class Meta:
        model = EventMembership

    event = factory.SubFactory(EventFactory)
    user = factory.SubFactory(UserFactory)
    role = "manager"
    permissions = {
        "activate_tickets": True,
        "verify_tickets": True,
        "create_batches": False,
        "void_batches": False
    }
    invited_by = factory.SubFactory(UserFactory)
    is_active = True


class TicketTypeFactory(DjangoModelFactory):
    class Meta:
        model = TicketType

    event = factory.SubFactory(EventFactory)
    name = factory.Sequence(lambda n: f"Ticket Type {n}")
    description = factory.Faker("sentence")
    price = factory.Faker("pydecimal", left_digits=3, right_digits=2, positive=True)
    is_active = True


class BatchFactory(DjangoModelFactory):
    class Meta:
        model = Batch

    event = factory.SubFactory(EventFactory)
    batch_number = factory.Sequence(lambda n: f"B{n:03d}")
    quantity = 100
    status = "active"
    created_by = factory.SubFactory(UserFactory)


class BatchMembershipFactory(DjangoModelFactory):
    class Meta:
        model = BatchMembership

    batch = factory.SubFactory(BatchFactory)
    membership = factory.SubFactory(EventMembershipFactory)
    can_activate = True
    can_verify = True
    is_active = True
    assigned_by = factory.SubFactory(UserFactory)


class TicketFactory(DjangoModelFactory):
    class Meta:
        model = Ticket

    batch = factory.SubFactory(BatchFactory)
    ticket_type = factory.SubFactory(TicketTypeFactory)
    short_code = factory.Sequence(lambda n: f"T{n:06d}")
    qr_code = factory.LazyAttribute(lambda obj: f"qr_{obj.short_code}")
    status = "unused"


class ScanLogFactory(DjangoModelFactory):
    class Meta:
        model = ScanLog

    ticket = factory.SubFactory(TicketFactory)
    qr_code = factory.LazyAttribute(lambda obj: obj.ticket.qr_code if obj.ticket else "test_qr")
    scan_type = "activate"
    result = "success"
    user = factory.SubFactory(UserFactory)
    gate = "Main Gate"
    ip_address = "127.0.0.1"
    user_agent = "Test Agent"
