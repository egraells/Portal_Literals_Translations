from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
import os

class Command(BaseCommand):
    help = 'Create a superuser if it does not exist, associate with UserProfile and Groups'

    def handle(self, *args, **kwargs):
        User = get_user_model()
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'adminpass')

        user, created = User.objects.get_or_create(username=username, defaults={'email': email})
        if created:
            user.set_password(password)
            user.is_superuser = True
            user.is_staff = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' created."))
        else:
            self.stdout.write(self.style.WARNING(f"Superuser '{username}' already exists."))

        # Associate Groups∫
        for group_name in ['Requester', 'Reviewer']:
            group, _ = Group.objects.get_or_create(name=group_name)
            user.groups.add(group)

        # Create or update UserProfile
        from xliff_manager.models import UserProfile  
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.save()

        self.stdout.write(self.style.SUCCESS(
            f"Superuser '{username}' is now a member of both 'Requester' and 'Reviewer' groups and has a UserProfile."
        ))

        from xliff_manager.models import Projects  # Adjust import if needed

        #  Associate UserProfile with ALL_PROJECTS
        all_projects, _ = Projects.objects.get_or_create(name='ALL_PROJECTS')
        profile.project = all_projects
        profile.save()

        self.stdout.write(self.style.SUCCESS(
            f"Superuser '{username}' is now associated with ALL_PROJECTS project."
))

