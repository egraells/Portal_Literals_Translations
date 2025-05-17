from django.db import migrations

def seed_projects(apps, schema_editor):
    Project = apps.get_model('xliff_manager', 'Projects')
    projects = [
        {'name': '1PSP'},
        {'name': '1QEM'},
        {'name': 'LEAP'},
        {'name': 'CellChain4X'},
        {'name': 'CellChain2X'},
    ]
    for proj in projects:
        Project.objects.get_or_create(name=proj['name'])

class Migration(migrations.Migration):

    dependencies = [
        ('xliff_manager', '002_languages_seed'),  
    ]

    operations = [
        migrations.RunPython(seed_projects),
    ]
