from django.db import models


class SaccoQuerySet(models.QuerySet):
    """Custom queryset for SACCO models with tenant filtering"""
    
    def for_sacco(self, sacco):
        """Filter by SACCO organization"""
        return self.filter(sacco=sacco)
    
    def active(self):
        """Filter active records"""
        return self.filter(is_active=True)


class SaccoManager(models.Manager):
    """Custom manager for SACCO models"""
    
    def get_queryset(self):
        return SaccoQuerySet(self.model, using=self._db)
    
    def for_sacco(self, sacco):
        return self.get_queryset().for_sacco(sacco)
    
    def active(self):
        return self.get_queryset().active()
