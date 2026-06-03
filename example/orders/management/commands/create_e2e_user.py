"""Create the E2E test superuser if it does not exist."""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the E2E test superuser"

    def handle(self, *args, **options):
        if not User.objects.filter(username="e2e_user").exists():
            User.objects.create_superuser(
                username="e2e_user",
                email="e2e@example.com",
                password="e2e_pass",
            )
            self.stdout.write(self.style.SUCCESS("Created e2e_user superuser"))
        else:
            self.stdout.write("e2e_user already exists")
