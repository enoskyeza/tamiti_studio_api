from django.db.models.signals import post_save
from django.dispatch import receiver

from tasks.models import Task
from finance.models import Requisition, Invoice, Payment

from .models import Notification


@receiver(post_save, sender=Task)
def task_created_notification(sender, instance, created, **kwargs):
    if created:
        user = instance.assigned_to or instance.created_by
        if user:
            Notification.objects.create(
                user=user,
                content=f"Task '{instance.title}' created",
                related_task=instance,
            )


@receiver(post_save, sender=Requisition)
def requisition_approved_notification(sender, instance, created, **kwargs):
    if not created and instance.status == "approved" and instance.approved_by:
        if instance.requested_by:
            Notification.objects.create(
                user=instance.requested_by,
                content="Requisition approved",
            )


@receiver(post_save, sender=Invoice)
def invoice_created_notification(sender, instance, created, **kwargs):
    if created:
        user = getattr(instance.party, "user", None)
        if user:
            Notification.objects.create(
                user=user,
                content=f"Invoice #{instance.id} created",
            )


@receiver(post_save, sender=Payment)
def payment_created_notification(sender, instance, created, **kwargs):
    if created:
        user = getattr(instance.party, "user", None)
        if user:
            Notification.objects.create(
                user=user,
                content=f"Payment of {instance.amount} recorded",
            )
