import pytest

from notifications.models import Notification
from tests.factories import (
    RequisitionFactory,
    InvoiceFactory,
    PaymentFactory,
    PartyFactory,
    UserFactory,
)


@pytest.mark.django_db
def test_requisition_approval_triggers_notification():
    requester = UserFactory()
    approver = UserFactory()
    requisition = RequisitionFactory(requested_by=requester, approved_by=None, status='pending')
    requisition.approve(approver)
    assert Notification.objects.filter(user=requester).count() == 1


@pytest.mark.django_db
def test_invoice_creation_triggers_notification():
    user = UserFactory()
    party = PartyFactory(user=user)
    InvoiceFactory(party=party)
    assert Notification.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_payment_creation_triggers_notification():
    user = UserFactory()
    party = PartyFactory(user=user)
    PaymentFactory(party=party)
    assert Notification.objects.filter(user=user).count() == 1
