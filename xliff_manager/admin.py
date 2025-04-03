from django.contrib import admin
from .models import Languages, TranslationsRequests, Translations_Units, ReviewRequests, LogDiary, CustomInstructions

# Per gestionar la base dades desde Admin Panel

class LanguagesAdmin(admin.ModelAdmin):
    pass

class TranslationsRequestsAdmin(admin.ModelAdmin):
    pass

class Translations_UnitsAdmin(admin.ModelAdmin):
    pass

class ReviewRequestsAdmin(admin.ModelAdmin):
    pass

class LogDiaryAdmin(admin.ModelAdmin):
    pass

class CustomInstructionsAdmin(admin.ModelAdmin):
    pass


admin.site.register(Languages, LanguagesAdmin) 
admin.site.register(TranslationsRequests, TranslationsRequestsAdmin) 
admin.site.register(Translations_Units, Translations_UnitsAdmin) 
admin.site.register(ReviewRequests, ReviewRequestsAdmin) 
admin.site.register(LogDiary, LogDiaryAdmin) 
admin.site.register(CustomInstructions, CustomInstructionsAdmin) 
# Register your models here.
