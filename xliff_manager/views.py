import os
import shutil
from datetime import datetime
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.http import FileResponse, HttpResponse
from django.contrib.auth import logout

from .models import Languages, TranslationsRequests, Translations_Units, ReviewRequests, LogDiary, CustomInstructions

from postmarker.core import PostmarkClient

ROOT_FOLDER = os.getenv("ROOT_FOLDER")
SEND_EMAILS = os.getenv("SEND_EMAILS")

def userpage(request):
    return render(request, 'xliff_manager/userpage.html')

def home(request):
    if not request.user.is_authenticated:
        return redirect('login')
    else:
        current_user = request.user
        pending_requests_count = ReviewRequests.objects.filter(business_user=current_user, status='Requested').count()
        context = {
            'pending_requests_count': pending_requests_count,
        }
        return render(request, 'xliff_manager/home.html', context)

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'xliff_manager/login.html', {'form': form})

@login_required
def download_file(request, type:str=None, id:str=None, file_to_download:str=None):
    if request.method == 'GET' and type == 'translations_request_AItranslated_file':
        return render(request, 'xliff_manager/download_file_confirmation.html', {
            'id': id,
            'file_to_download': file_to_download,
            'type': type,
        })
    
    if request.method == 'GET' and \
        (type in ["review_request_source_file", "review_request_target_file", "translations_request_AItranslated_file"]):
        file_path = os.path.join('review_requests', str(id), file_to_download)
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='application/force-download')
                response['Content-Disposition'] = f'attachment; filename="{file_to_download}"'
                return response
        else:
            return HttpResponse("File not found", status=404)
    
    if request.method == 'GET' and type == 'translations_request_original_file':
        file_path = os.path.join('translations_requests', str(id), file_to_download)
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='application/force-download')
                response['Content-Disposition'] = f'attachment; filename="{file_to_download}"'
                return response
        else:
            return HttpResponse("File not found", status=404)
    
    if request.method == 'GET' and type == 'translations_request_AItranslated_file_confirmed':
        file_path = os.path.join('translations_requests', str(id), file_to_download)
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='application/force-download')
                response['Content-Disposition'] = f'attachment; filename="{file_to_download}"'
                return response
        else:
            return HttpResponse("File not found", status=404)
    
    return HttpResponse("Invalid request", status=400)

def download_file_confirmed(request):
    if request.method == 'POST':
        type = request.POST.get('type')
        id = request.POST.get('id')
        file_to_download = request.POST.get('file_to_download')

        if type == 'translations_request_AItranslated_file_confirmed':
            file_path = os.path.join('translations_requests', str(id), file_to_download)
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    response = HttpResponse(f.read(), content_type='application/force-download')
                    response['Content-Disposition'] = f'attachment; filename="{file_to_download}"'
                    return response
            else:
                return HttpResponse("File not found", status=404)

def read_xliff_file(xliff_file):
    tree = ET.parse(xliff_file)
    root = tree.getroot()
    
    trans_units = []
    for unit in root.findall(".//trans-unit"):
        id = unit.get('id')
        source = unit.find('source').text
        target = unit.find('target').text
        trans_units.append({'id': id, 'source': source, 'target': target})
    
    file_element = root.find('file')  
    if file_element is not None:
        target_language = file_element.get('target-language')
    
    return trans_units, target_language

@login_required
def do_review_view(request, request_id):
    if request.method == 'GET':
        translations = Translations_Units.objects.filter(request_id=request_id)
        review_request = ReviewRequests.objects.get(id=request_id)
    
        return render (request, 'xliff_manager/review_business.html', {
            'review_request': review_request,
            'translations': translations,
       })

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == "save_changes":
            # Extracting all editable translations and comments
            trans_units_to_update = []
            for key in request.POST:
                if key.startswith("editable_translation_"):
                    index = key.split("_")[-1]  # Extract the counter value
                    trans_unit_id = request.POST.get(f"trans_unit_id_{index}", "")
                    
                    previous_reviewer_translation = request.POST.get(f"previous_reviewer_translation_{index}", "")
                    current_reviewer_translation = request.POST[key]
                    
                    previous_reviewer_comment = request.POST.get(f"previous_reviewer_comment_{index}", "")
                    current_reviewer_comment = request.POST.get(f"comments_{index}", "")  # Default to empty string if no comment 
                    
                    # Only for those that have been modified
                    if previous_reviewer_translation != current_reviewer_translation or \
                        previous_reviewer_comment != current_reviewer_comment:

                            trans_unit = Translations_Units.objects.get(id=trans_unit_id)
                            trans_unit.reviewer_translation = current_reviewer_translation if current_reviewer_translation is not None else ''
                            trans_unit.reviewer_comment = current_reviewer_comment if current_reviewer_comment is not None else ''
                            trans_unit.date_reviewed = timezone.now()
                            trans_units_to_update.append(trans_unit)

            # Bulk update all records at once and update the Request Review date
            if trans_units_to_update:
                Translations_Units.objects.bulk_update(trans_units_to_update, ["reviewer_translation", "reviewer_comment", "date_reviewed"])
                ReviewRequests.objects.filter(id=request_id).update(date_reviewed_by_business = timezone.now())
                # Log the action in the LogDiary
                LogDiary.objects.create(
                    user=request.user,
                    action="Saved_Custom_Translations",
                    review_request_id = request_id,
                )

                #TODO : canviar l'status a Saved Translations
            
            return render(request, 'xliff_manager/review_business_confirmation.html', 
                {'trans_units_updated': trans_units_to_update})

        
        if action == "decline_review":
            request_to_decline = ReviewRequests.objects.get(id=request_id)
            return render(request, 'xliff_manager/review_business_decline.html', 
                {'request': request_to_decline, 
                'user_confirmed' : False})
        
        if action == "decline_request_confirmed":
            justification = request.POST.get('justification')
            ReviewRequests.objects.filter(id=request_id).update(
                status = 'Declined', 
                date_declined = timezone.now(),
                decline_justification = justification if justification is not None else '')
            
            LogDiary.objects.create(
                    user=request.user,
                    action="Declined_Request",
                    review_request_id = request_id,
                    additional_info=justification,
            )
            
            request_declined = ReviewRequests.objects.get(id=request_id)

            """"
            send_email(recipient=request_reviewed.technical_user.email,
            subject='Request Declined',
            body=f'The user has declined the request id: {request_declined.id} with the justification: {request_declined.decline_justification}')
            """

            return render(request, 'xliff_manager/review_business_decline.html', 
                {'request': request_declined,
                 'user_confirmed' : True})
        
        request_done = None
        if action == "mark_as_reviewed":
            request_done = ReviewRequests.objects.get(id=request_id)
            return render(request, 'xliff_manager/review_business_done.html',
                {'request': request_done,
                'user_confirmed': False})

        if action == "mark_as_reviewed_confirmation":
            request_reviewed = ReviewRequests.objects.get(id=request_id)
            request_reviewed.status = 'Reviewed'
            request_reviewed.reviewer_comment = request.POST.get('reviwer_comment', '')
            request_reviewed.date_reviewed_by_business = timezone.now()
            request_reviewed.save()

            LogDiary.objects.create(
                    user=request.user,
                    action="Review_Marked_as_Reviewed",
                    review_request_id=f"{request_id}",
            )

            """
            send_email(recipient=request_reviewed.technical_user.email,
                        subject='Request Reviewed',
                        body=f'The user has reviewed the request id: {request_reviewed.id}')
            """

            return render(request, 'xliff_manager/review_business_done.html',
                {'request': request_done,
                 'user_confirmed': True})
        
        
@login_required
def request_translation_view(request):

    if request.method == 'GET':
        
        return render(request, 'xliff_manager/request_llm_translation.html', 
            {'languages': Languages.objects.all(),}
        )
    
    if request.method == 'POST' :
        action = request.POST.get('action')
        
        if action == 'translate_xliff':
            language_id = request.POST.get('language_selected')

            # Sanity check: Delete all files in the translations_requests folder
            for filename in os.listdir(ROOT_FOLDER):
                file_path = os.path.join(ROOT_FOLDER, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)

            trans_request = TranslationsRequests(
                language = Languages.objects.get(id=language_id),
                request_user = request.user,
                source_xliff_file = request.FILES['xliff_source_file'],
                target_xliff_file_name = request.FILES['xliff_source_file'].name + '_translated.xlf',
                literals_to_exclude_file = request.FILES['literal_ids_to_exclude_file'] if 'literal_ids_to_exclude_file' in request.FILES else None,
                literalpatterns_to_exclude_file = request.FILES['literal_patterns_to_exclude_file'] if 'literal_patterns_to_exclude_file' in request.FILES else None,
            )
            trans_request.save()

            # Move files this request to the folder with the Id 
            dest_folder = os.path.join(ROOT_FOLDER, str(trans_request.id)) 
            os.makedirs(dest_folder, exist_ok=True)

            source_xliff_file_only_name = os.path.basename(trans_request.source_xliff_file.name)
            shutil.move(trans_request.source_xliff_file.name, os.path.join(dest_folder, source_xliff_file_only_name))
            trans_request.source_xliff_file = source_xliff_file_only_name
            
            if trans_request.literals_to_exclude_file:
                exclude_file_name_only = os.path.basename(trans_request.literals_to_exclude_file.name)
                shutil.move(os.path.join(ROOT_FOLDER, exclude_file_name_only), 
                            os.path.join(dest_folder, exclude_file_name_only))
                trans_request.literals_to_exclude_file = exclude_file_name_only
            
            if trans_request.literalpatterns_to_exclude_file:
                exclude_patterns_file_name_only = os.path.basename(trans_request.literalpatterns_to_exclude_file.name)
                shutil.move(os.path.join(ROOT_FOLDER, exclude_patterns_file_name_only), 
                            os.path.join(dest_folder, exclude_patterns_file_name_only))
                trans_request.literalpatterns_to_exclude_file = exclude_patterns_file_name_only

            trans_request.save()

            LogDiary.objects.create(
                user = request.user, 
                action = "Requested_Translation_to_AI",
                translation_request_id = f"{trans_request.id}",
            )

            return render(request, 'xliff_manager/request_llm_confirmation.html', 
                {'trans_request': trans_request})
           
    else:
        return render(request, 'xliff_manager/request_llm_translation.html', 
            {'selected_language': 0})

@login_required
def choose_review_view(request):
    if request.method == 'GET':
        current_user_id = request.user.id 
        review_requests = ReviewRequests.objects.filter(business_user=current_user_id).order_by('-date_created')
        return render(request, 'xliff_manager/my_pending_reviews.html', 
            {'review_requests': review_requests})
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'review_selected':
            request_selected_id = request.POST.get('request_selected_id')
        
            LogDiary.objects.create(
                user=request.user,
                action="Visualizes_Request",
                review_request_id=request_selected_id,
            )
            
            return redirect('do_request_review', request_id=request_selected_id)

@login_required
def send_email(recipient: str, subject: str, body: str):
    if SEND_EMAILS:
        postmark = PostmarkClient(server_token='fa9cda4a-0124-4b7a-9ad3-aadf18636cae')
        postmark.emails.send(
        From='esteve.graells@novartis.com',
        To=recipient,
        Subject=subject,
        HtmlBody=f'<html><body><strong>{body}</body></html>'
)

@login_required
def request_review_view(request):
    if request.method == 'GET':
        tags_used = ReviewRequests.objects.values_list('info_tag', flat=True).distinct()
        reviewers = User.objects.filter(groups__name='Reviewer').values('id', 'first_name', 'last_name')
        return render(request, 'xliff_manager/request_review.html',
            {'reviewers': reviewers,
             'languages': Languages.objects.all(),
             'tags_used': tags_used})
                           
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'request_business_review':
            if request.FILES['xliff_translations_file'] and request.POST.get('business_reviewer'):
                language_selected = request.POST.get('language')
                language_id = Languages.objects.get(id=language_selected).id
                uploaded_xliff_file = request.FILES['xliff_translations_file']
                original_xliff_file_name = uploaded_xliff_file.name
                business_reviewer = request.POST.get('business_reviewer')
                reviewer = User.objects.get(id=business_reviewer)
                requester_comment = request.POST.get('requester_comments')
                tag = request.POST.get('tag')

                review_request = ReviewRequests(
                    language_id = language_id,
                    technical_user = request.user,
                    business_user = reviewer,
                    target_xliff_file = uploaded_xliff_file,
                    requester_comment = requester_comment,
                    info_tag = tag
                )
                review_request.save()

                # When saving the file, we need to move it to the review_requests concret folder
                review_request = ReviewRequests.objects.get(pk=review_request.pk)
                dest_folder = os.path.join('review_requests', str(review_request.id))
                dest_name = os.path.join(dest_folder, original_xliff_file_name)
                os.makedirs(dest_folder, exist_ok=True)
                shutil.move(review_request.target_xliff_file.name, dest_name)

                review_request.target_xliff_file = original_xliff_file_name
                review_request.save()

                trans_units, language_xliff_file = read_xliff_file(dest_name)
                
                # Save the translations to the database
                for unit in trans_units:
                    Translations_Units.objects.create(
                        request_id = review_request.id,
                        language_id = language_id,
                        salesforce_id = unit['id'], 
                        source = unit['source'],
                        ai_translation = unit['target'],
                        reviewer_translation = '',
                        date_ingested = timezone.now(),
                        date_reviewed = None
                    )

                # Log the action in the LogDiary
                LogDiary.objects.create(
                    user=request.user,
                    user_requested = business_reviewer,
                    action="Requested_Business_Review",
                    review_request_id=f"{review_request.id}",
                )

                # return HttpResponse(f"File uploaded successfully: {uploaded_xliff_file}, Release: {new_release}")
                return render(request, 'xliff_manager/review_request_confirmation.html', 
                    {
                        'request_id' : review_request.id,
                        'language': review_request.language.name,
                        'reviewer' : reviewer.first_name + " " + reviewer.last_name,
                        'num_records' : len (trans_units),
                        'business_reviewer' : reviewer.first_name + " " + reviewer.last_name
                    })

@login_required
def check_request_status_view(request):
    if request.method == 'GET':
        current_user = request.user
        translations_requests = TranslationsRequests.objects.filter(request_user=current_user).order_by('-date_created')
        review_requests = ReviewRequests.objects.filter(technical_user=current_user).order_by('-date_created')
        return render(request, 'xliff_manager/check_request_status.html', 
                      {'translations_requests': translations_requests,
                       'review_requests': review_requests})


@login_required
def diary_log_view(request):
    if request.method == 'GET':
        activity_list = LogDiary.objects.all()
        return render(request, 'xliff_manager/diary_log.html', 
            {'activity_list': activity_list})

@login_required
def load_translations(request):
    return render(request, '/')

@login_required
def custom_instructions_view(request):
    
    if request.method == 'GET':
        custom_instructions = CustomInstructions.objects.all().order_by('language__name')
        translations_adjusted_by_reviewers = []
        translations_with_differences = Translations_Units.objects.exclude(reviewer_translation__exact='').order_by('-date_reviewed')
        for translation in translations_with_differences:
            if translation.ai_translation is not None:
                translation.reviewer_translation = translation.reviewer_translation.strip()
                translation.reviewer_translation = translation.reviewer_translation.replace('\r', '').replace('\n', '')
            
            if translation.ai_translation is not None:
                translation.ai_translation = translation.ai_translation.strip()
                translation.ai_translation = translation.ai_translation.replace('\r', '').replace('\n', '')
            
            if translation.ai_translation != translation.reviewer_translation:
                translations_adjusted_by_reviewers.append(translation)

        return render(request, 'xliff_manager/custom_instructions.html', {
            'custom_instructions': custom_instructions,
            'translations_adjusted_by_reviewers': translations_adjusted_by_reviewers
        })

    if request.method == 'POST':
        action = request.POST.get('action')
        custom_instructions = []
        
        instruction_id = request.POST["instruction_id"]
        instruction_text = request.POST["instructions_modified"]
        custom_instruction = CustomInstructions.objects.get(id=instruction_id)
        custom_instruction.instructions = instruction_text
        custom_instruction.user_last_modification = request.user
        custom_instruction.save()

        # Log the action in the LogDiary
        LogDiary.objects.create(
            user = request.user,
            action = "Saved_Custom_Instructions",
        )
        
        return render(request, 'xliff_manager/custom_instructions_confirmation.html', {'num_records': len(custom_instructions)})


def confirm_insertion_view(request, num_records):
    return render(request, 'xliff_manager/confirm_insertion.html', {'num_records': num_records})


