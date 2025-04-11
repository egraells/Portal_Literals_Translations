import os
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.models import AbstractUser
from django.conf import settings

# Create your models here.
class Languages(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    lang_iso_value = models.CharField(max_length=10, null=True, blank=True)
    flag_iso_value = models.CharField(max_length=10, null=True, blank=True)
    emoji_flag = models.CharField(max_length=10, default="🌎")

    def __str__(self):
        return self.name

class TranslationsRequests(models.Model):

    def upload_to_folder(instance, filename):   
        #This function is not strictly necessary in this form, 
        # but it is useful to have it in case we need to change 
        # the folder structure in the future
        return os.path.join(settings.TRANS_REQUESTS_FOLDER, filename)
    
    id = models.AutoField(primary_key=True)
    language = models.ForeignKey('Languages', on_delete=models.CASCADE)
    request_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='request_user', null=False, blank=False)
    source_xliff_file = models.FileField(upload_to=upload_to_folder, blank=False)
    target_xliff_file_name = models.CharField(max_length=200, null=True, blank=True)
    prompt_addition_file = models.FileField(upload_to=upload_to_folder)
    literals_to_exclude_file = models.FileField(upload_to=upload_to_folder)
    literalpatterns_to_exclude_file = models.FileField(upload_to=upload_to_folder)
    date_created = models.DateTimeField(auto_now_add=True)
    date_sent_to_llm = models.DateTimeField(null=True, blank=True)    
    date_received_from_llm = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=100, default='Created') # Created, Sent_to_LLM, Received_from_LLM

    def save(self, *args, **kwargs):

        if self.status == 'Created':
            # Every time a new translation request is created, we need to send it to the LLM
            # Create a new thread to send translations to the LLM
            #print(f"Request Saved")
            #print(f"A New Thread Should be created to send the translations to the LLM")
            
            """
            def translation_thread():
                # Local import to avoid circular dependency
                from .aitranslator import main_translator as aitranslator
                aitranslator.execute_pending_requests(self)

            import threading
            translation_thread = threading.Thread(target=translation_thread)
            translation_thread.start()
            """

        elif self.status == 'Sent_to_LLM':
            self.date_sent_to_llm = timezone.now()
        elif self.status == 'Received_from_LLM':
            self.date_received_from_llm = timezone.now()
            LogDiary.objects.create(
                user=1,
                action="Translation_Received_from_LLM",
                review_request_id=f"{self.id}",
                additional_info=f"The LLM has resolved the request for the request Id: {self.id}. The user assigned is 1.",
            )
        else:
            print(f"ERROR: Unknown status: {self.status}")
        
        super().save(*args, **kwargs)

class ReviewRequests(models.Model):
    id = models.AutoField(primary_key=True)
    language = models.ForeignKey('Languages', on_delete=models.CASCADE)
    technical_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='technical_requester', null=False, blank=False) 
    business_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='business_receiver', null=False, blank=False) 
    target_xliff_file = models.FileField(blank=True)
    info_tag = models.TextField(null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_reviewed_by_business = models.DateTimeField(null=True, blank=True)
    date_declined = models.DateTimeField(null=True, blank=True)
    decline_justification = models.TextField(blank=True, null=True)
    requester_comment = models.TextField(blank=True, null=True)
    reviewer_comment = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=100, default='Requested') # Requested, Reviewed, Declined, Downloaded

class Translations_Units(models.Model):
    id = models.AutoField(primary_key=True)
    language = models.ForeignKey('Languages', on_delete=models.CASCADE)
    request = models.ForeignKey('ReviewRequests', on_delete=models.CASCADE)
    salesforce_id = models.TextField()
    reviewer_comment = models.TextField(null=True, blank=True)
    source = models.TextField()
    ai_translation = models.TextField(null=True, blank=True)
    reviewer_translation = models.TextField()
    date_ingested = models.DateTimeField(null=True, blank=True)
    date_reviewed = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.language} - {self.salesforce_id} - {self.source} - {self.ai_translation} - {self.reviewer_translation} - {self.date_ingested} - {self.date_reviewed}"


class LogDiary(models.Model):
    class Action(models.TextChoices): 
        Requested_Translation_to_AI = 'RRTTLLM', 'Requested_Translation_to_AI'   
        TRANSLATION_RECEIVED_FROM_LLM = 'TRFLLM', 'Translation_Received_from_LLM'  
        EN_REVISIO = 'RV', 'REvision'
    
    id = models.AutoField(primary_key=True)
    date = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    user_requested = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviewer', null=True, blank=True) 
    action = models.CharField(max_length=100) 
    review_request_id = models.IntegerField(null=True, blank=True)
    translation_request_id = models.IntegerField(null=True, blank=True)
    additional_info = models.TextField(null=True, blank=True)
    description = models.CharField(max_length=200, null=False, blank=False)
    accio = models.CharField(max_length=50, choices=Action, null=True, blank=True)

    class Meta: 
        ordering = ['-date']
        #indexes = [ models.Index(fields=['-publish']), ]  

    def __str__(self):
        return f"{self.user} - {self.action} - {self.date}"
    
    def save(self, *args, **kwargs):

        date_format = None
        if self.date is not None:
            date_format = {self.date.strftime('%Y-%m-%d %H:%M')}

        match self.action:
            case "Requested_Translation_to_AI":
                self.description = f"{self.additional_info}"
            case "Translation_Received_from_LLM":
                self.description = f"{self.additional_info}"
            case "Requested_Business_Review":
                self.description = f"{self.additional_info}"
            case "Visualizes_Request":
                self.description = f"{self.additional_info}"
            case "Declined_Request":
                self.description = f"{self.additional_info}"
            case "Review_Marked_as_Reviewed":
                self.description = f"{self.additional_info}"
            case "Requester_Downloaded_Review":
                self.description = f"{self.additional_info}"
            case "Saved_Custom_Translations":
                self.description = f"{self.additional_info}"
            case "Saved_Custom_Instructions":
                self.description = f"{self.additional_info}"   
            case _:
                self.description = f"Unknown action: {self.action} at {date_format}  - Additional Info: {self.additional_info}"
        
        super().save(*args, **kwargs)

class CustomInstructions(models.Model):
    
    id = models.AutoField(primary_key=True)
    user_last_modification = models.ForeignKey(User, on_delete=models.CASCADE)
    language = models.ForeignKey('Languages', on_delete=models.CASCADE)
    instructions = models.TextField(null=True, blank=True)
    date_last_modification = models.DateTimeField(auto_now=True)

    class Meta: 
        ordering = ['-date_last_modification']
        #indexes = [ models.Index(fields=['-publish']), ]  

    def __str__(self):
        return f"Custom instructions for {self.language} by {self.user_last_modification} in {self.date_last_modification}: {self.instructions}"   