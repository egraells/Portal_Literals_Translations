from django.contrib import admin
from .models import Projects, Languages, TranslationsRequests, Translations_Units, ReviewRequests, LogDiary, CustomInstructions, UserProfile

# Para gestionar en el Admin Panel

class ProjectsAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'date_created', 'date_last_modified')
    search_fields = ('name', 'description')
    list_filter = ('date_created', 'date_last_modified')
    list_display_links = ('name',)
    list_editable = ('description', )
    ordering = ('-date_created',)  # Order by date_created descending


class LanguagesAdmin(admin.ModelAdmin):
    list_display = ('name', 'lang_iso_value', 'flag_iso_value')
    list_display_links = ('name',)
    list_editable = ('lang_iso_value', 'flag_iso_value')


class TranslationsRequestsAdmin(admin.ModelAdmin):
    list_display = ('project', 'language', 'request_user', 'source_xliff_file', 'target_xliff_file_name', 'prompt_addition_file', 'literals_to_exclude_file', 'literalpatterns_to_exclude_file', 'date_created', 'date_started_on_llm', 'date_received_from_llm',  'status')
    list_filter = ('status', 'project')
    search_fields = ('technical_user__username', 'business_user__username', 'info_tag')
    list_display_links = ('request_user', 'project')
    list_editable = ('status',)

class Translations_UnitsAdmin(admin.ModelAdmin):
    list_display = ('language', 'request', 'salesforce_id', 'source', 'ai_translation', 'reviewer_translation', 'date_ingested', 'date_reviewed')
    list_filter = ('language', 'request')
    search_fields = ('salesforce_id', 'source', 'ai_translation', 'reviewer_translation')
    list_display_links = ('request', )

class ReviewRequestsAdmin(admin.ModelAdmin):
    list_display = ('project', 'language', 'technical_user', 'business_user', 'target_xliff_file', 'info_tag', 'date_created', 'date_reviewed_by_business', 'status')
    list_filter = ('technical_user', 'business_user', 'project')
    search_fields = ('technical_user__username', 'business_user__username', 'info_tag')
    list_display_links = ('technical_user', 'business_user', 'target_xliff_file')
    list_editable = ('status',)
    ordering = ('-date_created',)  # Order by date_created descending

class LogDiaryAdmin(admin.ModelAdmin):
    list_display = ('project', 'date', 'user', 'user_requested', 'action', 'review_request', 'translation_request', 'additional_info', 'description')
    list_display_links = ('user', 'review_request', 'translation_request')
    list_filter = ('project', 'date', 'user', 'action')
    search_fields = ('description', 'action', 'user__username', 'review_request__technical_user__username', 'translation_request__technical_user__username')
    list_editable = ('action', 'description')
    ordering = ('-date',)  # Order by date_created descending

class CustomInstructionsAdmin(admin.ModelAdmin):
    list_display = ('project', 'language', 'instructions')
    list_filter = ('project', 'language')
    search_fields = ('project', 'language')
    list_display_links = ('project', 'language')
    list_editable = ('instructions',)
    ordering = ('language',)  # Order by date_created descending

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'project')
    list_filter = ('project',)
    list_display_links = ('user',)
    list_editable = ('project',)

admin.site.register(Projects, ProjectsAdmin)
admin.site.register(Languages, LanguagesAdmin) 
admin.site.register(TranslationsRequests, TranslationsRequestsAdmin) 
admin.site.register(Translations_Units, Translations_UnitsAdmin) 
admin.site.register(ReviewRequests, ReviewRequestsAdmin) 
admin.site.register(LogDiary, LogDiaryAdmin) 
admin.site.register(CustomInstructions, CustomInstructionsAdmin) 
admin.site.register(UserProfile, UserProfileAdmin) 
# Register your models here.
