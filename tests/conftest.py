import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db import transaction


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    Automatically enable database access for all tests.
    This fixture runs for every test function.
    """
    pass


@pytest.fixture(autouse=True)
def clear_content_type_cache():
    """
    Clear ContentType cache before and after each test to prevent
    cross-test contamination.
    """
    ContentType.objects.clear_cache()
    yield
    ContentType.objects.clear_cache()


@pytest.fixture
def project_content_type():
    """Fixture to provide Project ContentType with proper cleanup"""
    from projects.models import Project
    return ContentType.objects.get_for_model(Project)


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """
    Custom database setup for test session.
    Ensures proper database state for all tests.
    """
    with django_db_blocker.unblock():
        # Load any necessary fixtures or perform setup
        call_command('migrate', '--run-syncdb', verbosity=0, interactive=False)


@pytest.fixture(autouse=True)
def clean_database_state(transactional_db):
    """
    Ensure clean database state for each test by using transactions.
    This helps prevent test isolation issues.
    """
    # Use a savepoint to ensure proper rollback, but handle broken transactions
    with transaction.atomic():
        sid = transaction.savepoint()
        try:
            yield
        finally:
            # Only attempt rollback if transaction is not broken
            try:
                transaction.savepoint_rollback(sid)
            except transaction.TransactionManagementError:
                # Transaction is broken, let Django handle cleanup
                pass
