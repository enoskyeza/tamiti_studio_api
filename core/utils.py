from django.shortcuts import get_object_or_404

def get_by_uuid_or_404(model, uuid):
    return get_object_or_404(model, uuid=uuid, is_deleted=False)
