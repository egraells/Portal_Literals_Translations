from django.db import migrations

def seed_languages(apps, schema_editor):
    Language = apps.get_model('xliff_manager', 'Languages')
    languages = [
        {'name': 'Mandarin Chinese', 'lang_iso_value': 'zh', 'flag_iso_value': 'cn'},
        {'name': 'Spanish', 'lang_iso_value': 'es', 'flag_iso_value': 'es'},
        {'name': 'English', 'lang_iso_value': 'en', 'flag_iso_value': 'gb'},
        {'name': 'Hindi', 'lang_iso_value': 'hi', 'flag_iso_value': 'in'},
        {'name': 'Arabic', 'lang_iso_value': 'ar', 'flag_iso_value': 'sa'},
        {'name': 'Bengali', 'lang_iso_value': 'bn', 'flag_iso_value': 'bd'},
        {'name': 'Portuguese', 'lang_iso_value': 'pt', 'flag_iso_value': 'pt'},
        {'name': 'Russian', 'lang_iso_value': 'ru', 'flag_iso_value': 'ru'},
        {'name': 'Japanese', 'lang_iso_value': 'ja', 'flag_iso_value': 'jp'},
        {'name': 'Western Punjabi', 'lang_iso_value': 'pa', 'flag_iso_value': 'pk'},
        {'name': 'Marathi', 'lang_iso_value': 'mr', 'flag_iso_value': 'in'},
        {'name': 'Telugu', 'lang_iso_value': 'te', 'flag_iso_value': 'in'},
        {'name': 'Turkish', 'lang_iso_value': 'tr', 'flag_iso_value': 'tr'},
        {'name': 'Korean', 'lang_iso_value': 'ko', 'flag_iso_value': 'kr'},
        {'name': 'French', 'lang_iso_value': 'fr', 'flag_iso_value': 'fr'},
        {'name': 'German', 'lang_iso_value': 'de', 'flag_iso_value': 'de'},
        {'name': 'Vietnamese', 'lang_iso_value': 'vi', 'flag_iso_value': 'vn'},
        {'name': 'Tamil', 'lang_iso_value': 'ta', 'flag_iso_value': 'in'},
        {'name': 'Urdu', 'lang_iso_value': 'ur', 'flag_iso_value': 'pk'},
        {'name': 'Javanese', 'lang_iso_value': 'jv', 'flag_iso_value': 'id'},
        {'name': 'Italian', 'lang_iso_value': 'it', 'flag_iso_value': 'it'},
        {'name': 'Gujarati', 'lang_iso_value': 'gu', 'flag_iso_value': 'in'},
    ]

    for lang in languages:
        Language.objects.get_or_create(
            lang_iso_value=lang['lang_iso_value'],
            defaults={
            'name': lang['name'],
            'flag_iso_value': lang['flag_iso_value']
            }
        )

class Migration(migrations.Migration):

    dependencies = [
        ('xliff_manager', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_languages),
    ]
