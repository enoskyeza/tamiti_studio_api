from django.core.management.base import BaseCommand
from accounts.models import StaffRole, StaffProfile, Department, Designation, Branch
from assistants.models import VACommand, DefaultResponse

class Command(BaseCommand):
    help = "Seed default virtual assistants and staff profiles"

    def handle(self, *args, **kwargs):
        # Setup required departments and designations
        field_dept, _ = Department.objects.get_or_create(name="Field Operations")
        finance_dept, _ = Department.objects.get_or_create(name="Finance")
        projects_dept, _ = Department.objects.get_or_create(name="Projects")
        mascot_dept, _ = Department.objects.get_or_create(name="Marketing")

        manager_desig, _ = Designation.objects.get_or_create(name="Manager")
        mascot_desig, _ = Designation.objects.get_or_create(name="Mascot")

        default_branch, _ = Branch.objects.get_or_create(name="Head Office")

        # Define the assistants
        assistants = [
            {
                "name": "Tami",
                "title": "Brand Mascot",
                "department": mascot_dept,
                "designation": mascot_desig,
                "prompt": "You are a witty and cheerful mascot representing Tamiti. Keep interactions light and fun.",
                "dashboard": "/dashboard",
            },
            {
                "name": "Tendo Kyeza",
                "title": "Project Manager",
                "department": projects_dept,
                "designation": manager_desig,
                "prompt": "You're a results-oriented project manager who tracks timelines, tasks, and dependencies.",
                "dashboard": "/projects",
            },
            {
                "name": "Jessica Cruz",
                "title": "Head of Finance",
                "department": finance_dept,
                "designation": manager_desig,
                "prompt": "You're a sharp finance lead who tracks goals, accounts, and disbursements.",
                "dashboard": "/finance",
            },
            {
                "name": "Alfred Butler",
                "title": "Head of Field Operations",
                "department": field_dept,
                "designation": manager_desig,
                "prompt": "You're a tactical lead managing field visits, lead conversions, and outreach.",
                "dashboard": "/field",
            },
            {
                "name": "Hope Nansubuga",
                "title": "Head Media",
                "department": Department.objects.get_or_create(name="People & HR")[0],
                "designation": manager_desig,
                "prompt": "You're a friendly HR assistant who manages onboarding, performance and motivation.",
                "dashboard": "/people",
            },
        ]

        for bot in assistants:
            role, _ = StaffRole.objects.get_or_create(title=bot["title"], is_virtual=True)
            profile, created = StaffProfile.objects.get_or_create(
                name=bot["name"],
                user=None,
                role=role,
                department=bot["department"],
                designation=bot["designation"],
                branch=default_branch,
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"✔ Created VA profile: {profile.name}"))

                DefaultResponse.objects.create(
                    assistant=role,
                    fallback_text=f"Hi, I'm {profile.name}. I'm currently offline but will respond soon."
                )

                VACommand.objects.create(
                    assistant=role,
                    trigger_text="give me a summary",
                    match_type="contains",
                    response_mode="text",
                    response_text=f"Here's your default summary from {profile.name}. More logic coming soon."
                )
            else:
                self.stdout.write(f"⚠ VA already exists: {profile.name}")
