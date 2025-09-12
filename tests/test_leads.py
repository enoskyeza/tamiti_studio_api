import pytest
from rest_framework.test import APIClient
from django.utils import timezone

from common.enums import PriorityLevel, FollowUpType
from tests.factories import VisitFactory, ZoneFactory, LeadFactory, LeadActionFactory


@pytest.mark.django_db
def test_lead_conversion():
    visit = VisitFactory()
    client = APIClient()
    client.force_authenticate(user=visit.rep)
    response = client.post(f"/api/field/visits/{visit.id}/convert_to_lead/")
    assert response.status_code == 200
    visit.refresh_from_db()
    assert visit.linked_lead is not None
    assert visit.linked_lead.business_name == visit.business_name

@pytest.mark.django_db
def test_zone_creation():
    zone = ZoneFactory()
    assert zone.name.startswith("Zone")


@pytest.mark.django_db
def test_lead_methods():
    lead = LeadFactory(priority=PriorityLevel.HIGH, lead_score=90)
    assert lead.is_hot_lead() is True
    lead.follow_up_date = timezone.now().date()
    assert lead.has_pending_follow_up() is True


@pytest.mark.django_db
def test_visit_conversion():
    visit = VisitFactory()
    assert visit.linked_lead is None
    lead = visit.convert_to_lead()
    assert lead is not None
    assert visit.linked_lead == lead


@pytest.mark.django_db
def test_lead_action_creation():
    action = LeadActionFactory()
    assert action.lead is not None
    assert action.created_by is not None
    assert action.type == FollowUpType.CALL
