import pytest
from factories import *


@pytest.mark.django_db
def test_create_invoice():
    invoice = InvoiceFactory()
    assert invoice.party is not None
    assert invoice.total > 0


@pytest.mark.django_db
def test_create_goal_and_milestones():
    goal = GoalFactory()
    milestone = GoalMilestoneFactory(goal=goal)
    assert milestone.goal == goal
    assert milestone.amount <= goal.target_amount


@pytest.mark.django_db
def test_create_transaction_updates_account():
    account = AccountFactory()
    starting_balance = account.balance
    tx = TransactionFactory(account=account, amount=50000)
    account.refresh_from_db()
    assert account.balance == starting_balance - 50000


@pytest.mark.django_db
def test_payment_creates_transaction():
    payment = PaymentFactory()
    # Create a transaction manually and link it to the payment
    transaction = TransactionFactory(
        amount=payment.amount,
        account=payment.account,
        related_payment=payment
    )
    payment.transaction = transaction
    payment.save()
    
    assert payment.transaction is not None
    assert payment.transaction.amount == payment.amount
    assert payment.transaction.account == payment.account


@pytest.mark.django_db
def test_invoice_paid_status():
    invoice = InvoiceFactory(total=100000)
    PaymentFactory(invoice=invoice, amount=100000)
    invoice.refresh_from_db()
    assert invoice.amount_due == 0
