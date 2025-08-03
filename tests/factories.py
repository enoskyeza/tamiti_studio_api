# tests/factories.py
from django.utils import timezone

import factory
from users.models import User
from factory.django import DjangoModelFactory
from projects.models import Project, Milestone, ProjectComment
from tasks.models import Task, TaskGroup
from field.models import Zone, Lead, Visit, LeadAction
from common.enums import *

from finance.models import (
    Party, Account, Invoice, Payment, Transaction, Goal, GoalMilestone, Requisition
)

from chatrooms.models import (
    Channel, ChannelMessage, ChannelMember,
    DirectThread, DirectMessage
)


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
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
        model = ProjectComment

    project = factory.SubFactory(ProjectFactory)
    user = factory.SubFactory(UserFactory)
    content = "This is a comment"


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
    number = factory.Faker('bank_account')
    type = AccountType.BANK
    balance = 100000
    currency = Currency.USD


class InvoiceFactory(DjangoModelFactory):
    class Meta:
        model = Invoice

    party = factory.SubFactory(PartyFactory)
    direction = InvoiceDirection.OUTGOING
    total_amount = 500000
    description = factory.Faker('sentence')
    issued_date = factory.LazyFunction(timezone.now)
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

    user1 = factory.SubFactory(UserFactory)
    user2 = factory.SubFactory(UserFactory)


class DirectMessageFactory(DjangoModelFactory):
    class Meta:
        model = DirectMessage

    thread = factory.SubFactory(DirectThreadFactory)
    sender = factory.SubFactory(UserFactory)
    content = factory.Faker("sentence")
    timestamp = factory.LazyFunction(timezone.now)
