import os
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.models import AbstractUser

ROOT_FOLDER = "translations_requests" #Should be externalized with the one in views.py


# Create your models here.
class Languages(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    iso_value = models.CharField(max_length=10)
    flag_url = models.URLField(max_length=200)
    emoji_flag = models.CharField(max_length=10, default="🌎")

    def __str__(self):
        return self.name

class TranslationsRequests(models.Model):

    def upload_to_folder(instance, filename):   
        #This function is not strictly necessary in this form, 
        # but it is useful to have it in case we need to change 
        # the folder structure in the future
        return os.path.join(ROOT_FOLDER, filename)
    
    id = models.AutoField(primary_key=True)
    language = models.ForeignKey('Languages', on_delete=models.CASCADE)
    request_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='request_user', null=False, blank=False) #TODO
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
    technical_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='technical_requester', null=False, blank=False) #TODO
    business_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='business_receiver', null=False, blank=False) #TODO
    target_xliff_file = models.FileField(upload_to='review_requests', blank=False)
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
    request = models.ForeignKey('ReviewRequests', on_delete=models.CASCADE)
    salesforce_id = models.TextField()
    reviewer_comment = models.TextField(null=True, blank=True)
    source = models.TextField()
    ai_translation = models.TextField(null=True, blank=True)
    reviewer_translation = models.TextField()
    date_ingested = models.DateTimeField(null=True, blank=True)
    date_reviewed = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.language} - {self.release}"


class LogDiary(models.Model):
    class Action(models.TextChoices): 
        REQUESTER_REQUEST_TRANSLATION_TO_LLM = 'RRTTLLM', 'Requester_Request_Translation_to_LLM'   
        TRANSLATION_RECEIVED_FROM_LLM = 'TRFLLM', 'Translation_Received_from_LLM'  
        EN_REVISIO = 'RV', 'REvision'
    
    id = models.AutoField(primary_key=True)
    date = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
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

        match self.action:
            case "Requester_Request_Translation_to_LLM":
                self.description = f"Translation requested (Translation Id Generated: {self.translation_request_id}) by {self.user} at {self.date} - Info: {self.additional_info}"
            case "Translation_Received_from_LLM":
                self.description = f"Translation received from LLM (Translation id: {self.translation_request_id}) - Info: {self.additional_info}"
            case "Requester_Requests_Business_Review":
                self.description = f"Review requested (Review Id generated: {self.review_request_id}) by {self.user} at {self.date} - Info: {self.additional_info}"
            case "Reviewer_Visualizes_Request":
                self.description = f"Review visualized (Review Id: {self.review_request_id}) by {self.user} at {self.date} - Info: {self.additional_info}"
            case "Reviewer_Saves_Custom_Translations":
                self.description = f"Translations saved {self.user} at {self.date} - Info: {self.additional_info}"
            case "Reviewer_Declines_Request":
                self.description = f"Review declined (Review Id: {self.review_request_id}) by {self.user} at {self.date} - Info: {self.additional_info}"
            case "Reviewer_Mark_as_Reviewed_Request":
                self.description = f"Review marked as reviewed (Review Id: {self.review_request_id}) by {self.user} at {self.date} - Info: {self.additional_info}"
            case "Requester_Downloaded_Review":
                self.description = f"Review downloaded (Review Id: {self.review_request_id}) by {self.user} at {self.date} - Info: {self.additional_info}"
            case "Custom_Instrucions_Modified":
                self.description = f"Review downloaded (Review Id: {self.review_request_id}) by {self.user} at {self.date} - Info: {self.additional_info}"
            case _:
                self.description = f"Unknown action: {self.action} at {self.date} - Info: {self.additional_info}"
        
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