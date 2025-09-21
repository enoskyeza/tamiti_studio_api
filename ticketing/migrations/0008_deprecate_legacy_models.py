from django.db import migrations


class Migration(migrations.Migration):
    """
    Migration to mark legacy models as deprecated.
    This doesn't remove them yet to maintain backward compatibility,
    but adds deprecation warnings and prepares for future removal.
    """
    
    dependencies = [
        ('ticketing', '0007_migrate_to_unified_membership'),
    ]

    operations = [
        # SQLite doesn't support COMMENT ON TABLE, so we'll just mark this as a deprecation migration
        # The deprecation is handled in the admin interface and documentation
        migrations.RunSQL(
            "SELECT 1;",  # No-op SQL that works on all databases
            reverse_sql="SELECT 1;"
        ),
    ]
