# users/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User
from accounts.models import StaffProfile, CustomerProfile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.role == User.Role.STAFF and not hasattr(instance, 'staff_profile'):
            StaffProfile.objects.create(user=instance)
        elif instance.role == User.Role.CUSTOMER and not hasattr(instance, 'customer_profile'):
            CustomerProfile.objects.create(user=instance)
