from django.db import models
from django.utils import timezone
from users.models import User
from core.models import BaseModel
from common.enums import PriorityLevel, LeadStage, LeadSource, VisitOutcome, FollowUpType, LeadStatus


class Zone(BaseModel):
    name = models.CharField(max_length=100)
    region = models.CharField(max_length=100, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.name


class Lead(BaseModel):
    business_name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=20)
    contact_email = models.EmailField(blank=True, null=True)
    status = models.CharField(max_length=50, choices=LeadStatus.choices, default=LeadStatus.NEW)
    stage = models.CharField(max_length=50, choices=LeadStage.choices, default=LeadStage.PROSPECT)
    source = models.CharField(max_length=100, choices=LeadSource.choices, blank=True)
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True)
    assigned_rep = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_leads')
    products_discussed = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    follow_up_type = models.CharField(max_length=50, choices=FollowUpType.choices, blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    lead_score = models.IntegerField(default=0)
    priority = models.CharField(max_length=50, choices=PriorityLevel.choices, default=PriorityLevel.MEDIUM)
    documents = models.FileField(upload_to='leads/docs/', blank=True, null=True)
    tags = models.CharField(max_length=255, blank=True, help_text="Comma-separated tags like #vip,#hot")

    def __str__(self):
        return self.business_name

    def has_pending_follow_up(self):
        return self.follow_up_date and self.follow_up_date >= timezone.now().date()

    def is_hot_lead(self):
        return self.priority in [PriorityLevel.HIGH, PriorityLevel.URGENT] or self.lead_score >= 80

    class Meta:
        ordering = ['-created_at', '-id']


class LeadAction(BaseModel):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='actions')
    type = models.CharField(max_length=50, choices=FollowUpType.choices)
    date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    outcome = models.CharField(max_length=100, blank=True)
    next_follow_up = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.type} with {self.lead.business_name} on {self.date.strftime('%Y-%m-%d')}"


class Visit(BaseModel):
    rep = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True)
    location = models.CharField(max_length=255)
    date_time = models.DateTimeField(default=timezone.now)
    business_name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=20)
    contact_email = models.EmailField(blank=True, null=True)
    products_discussed = models.JSONField(default=list, blank=True)
    visit_outcome = models.CharField(max_length=100, choices=VisitOutcome.choices, blank=True)
    feedback_notes = models.TextField(blank=True)
    follow_up_type = models.CharField(max_length=50, choices=FollowUpType.choices, blank=True)
    follow_up_date = models.DateField(null=True, blank=True)
    next_step_agreed = models.TextField(blank=True)
    prompt_given = models.BooleanField(default=False)
    customer_agreed_contact = models.BooleanField(default=True)
    add_as_lead = models.BooleanField(default=False)
    code_verified = models.BooleanField(default=False)
    linked_lead = models.OneToOneField(Lead, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"Visit: {self.business_name} on {self.date_time.strftime('%Y-%m-%d')}"

    def convert_to_lead(self):
        if self.add_as_lead and not self.linked_lead:
            lead = Lead.objects.create(
                business_name=self.business_name,
                contact_name=self.contact_name,
                contact_phone=self.contact_phone,
                contact_email=self.contact_email,
                zone=self.zone,
                assigned_rep=self.rep,
                products_discussed=self.products_discussed,
                notes=self.feedback_notes,
                follow_up_type=self.follow_up_type,
                follow_up_date=self.follow_up_date,
                source=LeadSource.FIELD
            )
            self.linked_lead = lead
            self.save()
            return lead
        return self.linked_lead

    class Meta:
        ordering = ['-date_time', '-created_at', '-id']
