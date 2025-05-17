from django.db import migrations

def seed_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    groups = ['Requester', 'Reviewer']
    for group_name in groups:
        Group.objects.get_or_create(name=group_name)

class Migration(migrations.Migration):

    dependencies = [
        ('xliff_manager', '003_projects_seed'),  
    ]

    operations = [
        migrations.RunPython(seed_groups),
    ]
