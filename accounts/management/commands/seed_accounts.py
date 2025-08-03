# accounts/management/commands/seed_accounts.py

from django.core.management.base import BaseCommand
from accounts.models import Branch, Department, Designation

class Command(BaseCommand):
    help = "Seed initial data for Branches, Departments, and Designations"

    def handle(self, *args, **kwargs):
        self.stdout.write("🔄 Seeding core account data...")

        # Branch
        branch_name = "Head Office"
        branch, created = Branch.objects.get_or_create(name=branch_name)
        self.stdout.write(f"{'✅ Created' if created else '⚠️ Exists'} Branch: {branch.name}")

        # Departments
        departments = ["Finance", "Projects", "Digital", "Content", "Admin", "Sales", "Development", "Marketing", "Field Operations"]
        for name in departments:
            dept, created = Department.objects.get_or_create(name=name)
            self.stdout.write(f"{'✅ Created' if created else '⚠️ Exists'} Department: {dept.name}")

        # Designations
        designations = ["Manager", "Mascot", "Officer", "Assistant", "Field Agent", "Designer", "Developer", "Executive"]
        for name in designations:
            desig, created = Designation.objects.get_or_create(name=name)
            self.stdout.write(f"{'✅ Created' if created else '⚠️ Exists'} Designation: {desig.name}")

        self.stdout.write(self.style.SUCCESS("🎉 Seeding complete!"))
