from django.db.models.signals import post_save, post_delete, pre_save, pre_delete
from django.dispatch import receiver

from finance.models import Requisition, Invoice, Payment
from tasks.models import Task
from users.models import User
from .models import Notification


# --- Utility function -----------------------------------------------------

def _notify(actor, recipient, verb, target=None, url=""):
    if recipient is None:
        return
    Notification.objects.create(
        actor=actor,
        recipient=recipient,
        verb=verb,
        target=target,
        url=url,
    )


# --- Requisition Signals --------------------------------------------------

@receiver(pre_save, sender=Requisition)
def cache_requisition_status(sender, instance, **kwargs):
    if instance.pk:
        previous = sender.objects.only('status').get(pk=instance.pk)
        instance._previous_status = previous.status


@receiver(post_save, sender=Requisition)
def requisition_approval_notification(sender, instance, created, **kwargs):
    if created or instance.status != 'approved':
        return
    if getattr(instance, '_previous_status', None) == 'approved':
        return
    instance = sender.objects.select_related('requested_by', 'approved_by').get(pk=instance.pk)
    _notify(
        actor=instance.approved_by,
        recipient=instance.requested_by,
        verb="approved your requisition",
        target=instance,
        url=f"/finance/requisitions/{instance.pk}/",
    )


# --- Task Signals ---------------------------------------------------------

@receiver(pre_save, sender=Task)
def cache_task_assignment(sender, instance, **kwargs):
    if instance.pk:
        previous = sender.objects.select_related('assigned_to').get(pk=instance.pk)
        instance._previous_assigned_to = previous.assigned_to


@receiver(post_save, sender=Task)
def task_notifications(sender, instance, created, **kwargs):
    instance = sender.objects.select_related('assigned_to', 'created_by').get(pk=instance.pk)
    if created:
        user = instance.assigned_to or instance.created_by
        if user:
            _notify(
                actor=instance.created_by,
                recipient=user,
                verb="created a task",
                target=instance,
                url=f"/tasks/{instance.pk}/",
            )
    else:
        previous_user = getattr(instance, '_previous_assigned_to', None)
        if instance.assigned_to and instance.assigned_to != previous_user:
            _notify(
                actor=instance.created_by,
                recipient=instance.assigned_to,
                verb="assigned you to a task",
                target=instance,
                url=f"/tasks/{instance.pk}/",
            )
        if previous_user and previous_user != instance.assigned_to:
            _notify(
                actor=instance.created_by,
                recipient=previous_user,
                verb="unassigned you from a task",
                target=instance,
                url=f"/tasks/{instance.pk}/",
            )


@receiver(pre_delete, sender=Task)
def cache_task_assignee_for_delete(sender, instance, **kwargs):
    if instance.assigned_to_id and not hasattr(instance, 'assigned_to'):
        instance.assigned_to = User.objects.only('id').get(pk=instance.assigned_to_id)
    if instance.created_by_id and not hasattr(instance, 'created_by'):
        instance.created_by = User.objects.only('id').get(pk=instance.created_by_id)


@receiver(post_delete, sender=Task)
def task_delete_notification(sender, instance, **kwargs):
    if getattr(instance, 'assigned_to', None):
        _notify(
            actor=getattr(instance, 'created_by', None),
            recipient=instance.assigned_to,
            verb="deleted a task assigned to you",
            target=None,
        )


# --- Invoice Signals ------------------------------------------------------

@receiver(post_save, sender=Invoice)
def invoice_created_notification(sender, instance, created, **kwargs):
    if not created:
        return
    instance = sender.objects.select_related('party__user').get(pk=instance.pk)
    user = getattr(instance.party, 'user', None)
    if user:
        _notify(
            actor=None,
            recipient=user,
            verb=f"created an invoice",
            target=instance,
            url=f"/finance/invoices/{instance.pk}/",
        )


# --- Payment Signals ------------------------------------------------------

@receiver(post_save, sender=Payment)
def payment_created_notification(sender, instance, created, **kwargs):
    if not created:
        return
    instance = sender.objects.select_related('requisition__requested_by', 'requisition__approved_by').get(pk=instance.pk)
    req = instance.requisition
    if req and req.requested_by:
        _notify(
            actor=req.approved_by,
            recipient=req.requested_by,
            verb="confirmed payment",
            target=instance,
            url=f"/finance/payments/{instance.pk}/",
        )
