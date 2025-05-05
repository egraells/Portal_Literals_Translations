import os
from datetime import datetime
import xml.etree.ElementTree as ET
from urllib.parse import unquote

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone
from django.http import HttpResponse
from django.shortcuts import render, redirect

from django.core.files.storage import FileSystemStorage

from .models import Languages, TranslationsRequests, Translations_Units, ReviewRequests, LogDiary, CustomInstructions

from postmarker.core import PostmarkClient

from django.core.mail import send_mail

if settings.SEND_EMAILS:
    #send_mail('Test', 'This is a test', 'esteve.graells@proton.me',['esteve.graells@gmail.com'],fail_silently=False)
    pass

timespan = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
settings.LOGGER.debug(f"From settings.py TRANS_REQUESTS_FOLDER: {settings.TRANS_REQUESTS_FOLDER}, settings.SEND_EMAILS: {settings.SEND_EMAILS}")

            
def userpage(request):
    return render(request, 'xliff_manager/userpage.html')

def home(request):
    if not request.user.is_authenticated:
        return redirect('login')
    else:
        current_user = request.user
        pending_requests_count = ReviewRequests.objects.filter(
            business_user=current_user, 
            status__in=['Requested', 'Saved_Custom_Translations']
        ).count()
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

def is_user_allowed_to_download(user, type, id):
    # Check if the user is allowed to download the file based on the type and id
    
    user_data = User.objects.select_related('userprofile__project').get(id=user.id)
    if  type in ['translations_request_AItranslated_file', 'translations_request_original_file', 'translations_request_AItranslated_file_confirmed']:
            trans_request_associated_project = TranslationsRequests.objects.get(id=id).project
            return user_data.userprofile.project.id == trans_request_associated_project.id or user.is_superuser or user.is_staff
    
    elif type in ['review_request_source_file', 'review_request_target_file']:
        review_request_associated_project = ReviewRequests.objects.get(id=id).project 
        return user_data.userprofile.project.id == review_request_associated_project.id or user.is_superuser or user.is_staff
    
def id_exists(id, type):
    # Check if the user is allowed to download the file based on the type and id
    
    if  type in ['translations_request_AItranslated_file', 'translations_request_original_file', 'translations_request_AItranslated_file_confirmed']:
        return TranslationsRequests.objects.filter(id=id).exists()
    
    elif type in ['review_request_source_file', 'review_request_target_file']:
        return ReviewRequests.objects.filter(id=id).exists()
    

@login_required
def download_file(request, type:str=None, id:str=None, file_to_download:str=None):

    user_data = User.objects.select_related('userprofile__project').get(id=request.user.id)
    user_project = user_data.userprofile.project

    if not id_exists(id, type):
        return HttpResponse("The Id requested does not exist", status=400)
        
    if not is_user_allowed_to_download(request.user, type, id):
        return HttpResponse("You are not allowed to download the requested file", status=400)

    # Requires explicit confirmation from the user to comply with Novartis SOP
    if request.method == 'GET' and type == 'translations_request_AItranslated_file':
        return render(request, 'xliff_manager/download_file_confirmation.html', {
            'id': id, 'file_to_download': file_to_download, 'type': type,
        })
    
    elif request.method == 'GET' and (type in ["review_request_source_file", 
                                                "translations_request_original_file", 
                                                "translations_request_AItranslated_file_confirmed"]):
        
        # Build the right path
        if type == 'review_request_source_file':
            file_path = os.path.join(settings.MEDIA_ROOT, settings.REV_REQUESTS_FOLDER, str(id), file_to_download)
        elif type in ['translations_request_AItranslated_file_confirmed', 'translations_request_original_file']:
            file_path = os.path.join(settings.MEDIA_ROOT, settings.TRANS_REQUESTS_FOLDER, str(id), file_to_download)

        settings.LOGGER.debug(f"File path to download: {file_path}")
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                response = HttpResponse(f.read(), content_type='application/force-download')
                response['Content-Disposition'] = f'attachment; filename="{file_to_download}"'

                # Only a change status is made when the requester downloads the file reviewed, as
                # the reviewer will not be able to change the translations anymore
                if type == 'Requester_Downloaded_Review':
                    ReviewRequests.objects.filter(id=id).update(status = 'Requester_Downloaded_Review')
        
            # Update Log
            if type == 'review_request_source_file':
                LogDiary.objects.create(user = request.user, action = type, review_request_id = id, project = user_project, additional_info=f"File downloaded: {file_to_download}")
            elif type in ['translations_request_original_file', 'translations_request_AItranslated_file_confirmed']:
                LogDiary.objects.create(user = request.user, action = type, translation_request_id = id, project = user_project, additional_info=f"File downloaded: {file_to_download}")

            return response
        
    elif type == 'review_request_target_file':
        # Cal construir el fitxer amb les modificacions del usuari

        # From the review_request model obtains the target_xliff_file
        review_request = ReviewRequests.objects.get(id=id)
        xliff_file_path_url = review_request.target_xliff_file.url #/media/filename.xliff
        xliff_file_name = unquote(xliff_file_path_url.replace('/media/', '', 1))
        xliff_file_path = os.path.join(settings.MEDIA_ROOT, settings.REV_REQUESTS_FOLDER, str(id), xliff_file_name)

        # Fetch all translation units where ai_translation and reviewer_translation differ
        translation_units = Translations_Units.objects.filter(
            request_id=id
        ).exclude(reviewer_translation__exact='')
        user_modified_trans_unit_ids = translation_units.values_list('salesforce_id', flat=True)

        if os.path.exists(xliff_file_path):
            with open(xliff_file_path, 'rb') as f:
                tree = ET.parse(f)
                root = tree.getroot()
                
                trans_units = []
                for unit in root.findall(".//trans-unit"):
                    trans_unit_id = unit.get('id')
                    if trans_unit_id in user_modified_trans_unit_ids:
                        target_node = unit.find('target')
                        reviewer_translation = translation_units.get(salesforce_id=trans_unit_id).reviewer_translation
                        target_node.text = reviewer_translation

                # Generate the reviewed file    
                # Write the modified tree to a new XML file
                reviewed_file_path = os.path.join(settings.MEDIA_ROOT, settings.REV_REQUESTS_FOLDER, str(id), f"user_reviewed_{xliff_file_name}")
                tree.write(reviewed_file_path, encoding='utf-8', xml_declaration=True)

                LogDiary.objects.create(user=request.user, action = 'Downloaded_Reviewed_File', review_request_id = id if id is not None else '', 
                    project = user_project, additional_info=f"File downloaded: {file_to_download}")

                # Return the reviewed file as a downloadable response
                with open(reviewed_file_path, 'rb') as reviewed_file:
                    response = HttpResponse(reviewed_file.read(), content_type='application/force-download')
                    response['Content-Disposition'] = f'attachment; filename="reviewed_{xliff_file_name}"'
                    return response
    else:    
        return HttpResponse("File not found", status=404)
            
    return HttpResponse("Invalid request", status=400)

@login_required
def download_file_confirmed(request):
    user_data = User.objects.select_related('userprofile__project').get(id=request.user.id)
    user_project = user_data.userprofile.project

    if request.method == 'POST':
        type = request.POST.get('type')
        id = request.POST.get('id')
        file_to_download = request.POST.get('file_to_download')

        if type == 'translations_request_AItranslated_file_confirmed':
            file_path = os.path.join(settings.MEDIA_ROOT, settings.TRANS_REQUESTS_FOLDER, str(id), file_to_download)
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    response = HttpResponse(f.read(), content_type='application/force-download')
                    response['Content-Disposition'] = f'attachment; filename="{file_to_download}"'
                    LogDiary.objects.create(user=request.user, action="Downloaded_AI_Translations", project = user_project,
                        additional_info=f"File downloaded: {file_to_download}",  translation_request_id = id)
                    return response
            else:
                settings.LOGGER.error(f"[{timespan}] File not found: {file_path}")
                return HttpResponse("File not found", status=404)

def read_xliff_file(xliff_file):
    try: 
        tree = ET.parse(xliff_file)
        root = tree.getroot()
        trans_units = []
        for unit in root.findall(".//trans-unit"):
            id = unit.get('id')
            source = unit.find('source').text
            target = unit.find('target').text if unit.find('target') is not None else ''
            trans_units.append({'id': id, 'source': source, 'target': target})
        
        file_element = root.find('file')  
        if file_element is not None:
            target_language = file_element.get('target-language')
        
        return trans_units, target_language
    
    except ET.ParseError as e:
        settings.LOGGER.error(f"[{timespan}] Error parsing XLIFF file: {e}")
        return 0, None

@login_required
def do_review_view(request, request_id):
    # Get all user details using pre-fetching
    # Altra manera de fer-ho és: project = request.user.userprofile.project
    
    user_data = User.objects.select_related('userprofile__project').get(id=request.user.id)
    user_project = user_data.userprofile.project
    
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
                ReviewRequests.objects.filter(id=request_id).update(date_reviewed_by_business = timezone.now(), status = 'Saved_Custom_Translations' )

                # Log the action in the LogDiary
                LogDiary.objects.create(user=request.user, action="Saved_Custom_Translations", project=user_project, review_request_id=request_id)

            return render(request, 'xliff_manager/review_business_confirmation.html', 
                {'trans_units_updated': trans_units_to_update})

        if action == "decline_review":
            request_to_decline = ReviewRequests.objects.get(id=request_id)
            return render(request, 'xliff_manager/review_business_decline.html', 
                {'request': request_to_decline, 'user_confirmed' : False})
        
        if action == "decline_request_confirmed":
            justification = request.POST.get('justification')
            ReviewRequests.objects.filter(id=request_id).update(
                status = 'Declined', 
                date_declined = timezone.now(),
                decline_justification = justification if justification is not None else '')
            
            LogDiary.objects.create(user=request.user, action="Declined_Request", review_request_id = request_id, project = user_project, additional_info=justification)
            
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

            LogDiary.objects.create(user=request.user, action="Review_Marked_as_Reviewed", project=user_project, review_request_id=f"{request_id}")

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
        languages = Languages.objects.all().order_by('name')
        return render(request, 'xliff_manager/request_llm_translation.html', 
            {'languages': languages,}
        )
    
    if request.method == 'POST' :
        action = request.POST.get('action')
        
        if action == 'translate_xliff':
            language_id = request.POST.get('language_selected')
            source_xliff_file = request.FILES['xliff_source_file']
            literals_to_exclude_file = request.FILES.get('literal_ids_to_exclude_file')
            literalpatterns_to_exclude_file = request.FILES.get('literal_patterns_to_exclude_file')

            trans_units, target_language = read_xliff_file(source_xliff_file)

            user_data = User.objects.select_related('userprofile__project').get(id=request.user.id)
            user_project = user_data.userprofile.project

            if (len(trans_units) > 0 and target_language is not None):
                trans_request = TranslationsRequests(
                    language = Languages.objects.get(id=language_id),
                    project = user_project,
                    request_user = request.user,
                    source_xliff_file = source_xliff_file.name, 
                    target_xliff_file_name = source_xliff_file.name + '_translated.xlf',
                    literals_to_exclude_file = literals_to_exclude_file.name if literals_to_exclude_file else None,
                    literalpatterns_to_exclude_file = literalpatterns_to_exclude_file.name if literalpatterns_to_exclude_file else None,
                )
                trans_request.save()

                location = os.path.join(settings.MEDIA_ROOT, settings.TRANS_REQUESTS_FOLDER, str(trans_request.id))
                settings.LOGGER.debug(f"This folder will be used to upload the files: {location}")

                # Create the directory if it doesn't exist
                if not os.path.exists(location):
                    os.makedirs(location, exist_ok=True)
                    os.chmod(location, 0o777)  # 777 means read/write/exec for everyone (for folders)

                # Create the FileSystemStorage
                fs = FileSystemStorage(location=location, base_url=settings.MEDIA_URL + settings.TRANS_REQUESTS_FOLDER + f'/{trans_request.id}/')

                # Save the files to the upload directory
                if source_xliff_file:
                    source_xliff_filename = fs.save(source_xliff_file.name, source_xliff_file)
                    trans_request.source_xliff_file = source_xliff_filename
                
                    # Create a folder called "partial_files" inside the location folder
                    partials_folder = os.path.join(location, "partial_files")
                    os.makedirs(partials_folder, exist_ok=True)
                    permissions = 0o777  # 777 means read/write/exec for everyone (for folders)
                    os.chmod(partials_folder, permissions)

                if literals_to_exclude_file:
                    exclude_filename = fs.save(literals_to_exclude_file.name, literals_to_exclude_file)
                    trans_request.literals_to_exclude_file = exclude_filename

                if literalpatterns_to_exclude_file:
                    exclude_patterns_filename = fs.save(literalpatterns_to_exclude_file.name, literalpatterns_to_exclude_file)
                    trans_request.literalpatterns_to_exclude_file = exclude_patterns_filename

                trans_request.save()

                LogDiary.objects.create(user=request.user, action="Requested_Translation_to_AI", project=user_project, translation_request_id = f"{trans_request.id}")

                return render(request, 'xliff_manager/request_llm_confirmation.html', 
                    {'trans_request': trans_request})
           
            else:
                return render(request, 'xliff_manager/request_llm_translation_error.html')

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
    
    user_data = User.objects.select_related('userprofile__project').get(id=request.user.id)
    user_project = user_data.userprofile.project

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'review_selected':
            request_selected_id = request.POST.get('request_selected_id')
            LogDiary.objects.create(user=request.user, action="Visualizes_Request", project = user_project, review_request_id=request_selected_id)
            return redirect('do_request_review', request_id=request_selected_id)

@login_required
def send_email(recipient: str, subject: str, body: str):
    """
    if settings.SEND_EMAILS:
        postmark = PostmarkClient(server_token='fa9cda4a-0124-4b7a-9ad3-aadf18636cae')
        postmark.emails.send(
        From='esteve.graells@novartis.com',
        To=recipient,
        Subject=subject,
        HtmlBody=f'<html><body><strong>{body}</body></html>'
    )"""

@login_required
def request_review_view(request):
    user_data = User.objects.select_related('userprofile__project').get(id=request.user.id)
    user_project = user_data.userprofile.project

    if request.method == 'GET':
        return render(request, 'xliff_manager/request_review.html',
            {'reviewers': User.objects.filter(groups__name='Reviewer', userprofile__project=user_project).values('id', 'first_name', 'last_name').order_by('first_name', 'last_name'),
             'languages': Languages.objects.all().order_by('name'),
             'tags_used': ReviewRequests.objects.values_list('info_tag', flat=True).distinct().order_by('date_created')
            })
                           
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'request_business_review':
            if request.FILES['xliff_translations_file'] and request.POST.get('business_reviewer'):
                project = user_project
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
                    project = user_project,
                    #target_xliff_file = uploaded_xliff_file,
                    requester_comment = requester_comment,
                    info_tag = tag
                )
                review_request.save()

                # Create a FileSystemStorage instance for the upload directory within MEDIA_ROOT

                location = os.path.join(settings.MEDIA_ROOT, settings.REV_REQUESTS_FOLDER, str(review_request.id))
                settings.LOGGER.debug(f"This folder will be used to upload the review file: {location}")

                # Create the directory if it doesn't exist
                if not os.path.exists(location):
                    os.makedirs(location, exist_ok=True)
                    os.chmod(location, 0o664)  # 664 means read/write for owner and group, read for others 

                # Create the FileSystemStorage
                fs = FileSystemStorage(location=location, base_url=settings.MEDIA_URL + settings.REV_REQUESTS_FOLDER + f'/{review_request.id}/')

                # Save the uploaded file
                target_xliff_filename = fs.save(uploaded_xliff_file.name, uploaded_xliff_file)
                review_request.target_xliff_file = target_xliff_filename
                review_request.save()

                dest_name = os.path.join(location, target_xliff_filename)

                trans_units, language_xliff_file = read_xliff_file(dest_name)

                review_request.target_xliff_file = original_xliff_file_name
                review_request.save()

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
                LogDiary.objects.create(user=request.user, user_requested=User.objects.get(id=business_reviewer),
                    project = user_project, action="Requested_Business_Review", review_request_id=f"{review_request.id}")

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
    user_data = User.objects.select_related('userprofile__project').get(id=request.user.id)
    user_project = user_data.userprofile.project
    if request.method == 'GET':
        activity_list = LogDiary.objects.filter(project=user_project) if user_project.id > 0 else LogDiary.objects.all()
        return render(request, 'xliff_manager/diary_log.html', 
            {'activity_list': activity_list})

@login_required
def load_translations(request):
    return render(request, '/')

@login_required
def custom_instructions_view(request):
    user_data = User.objects.select_related('userprofile__project').get(id=request.user.id)
    user_project = user_data.userprofile.project
    
    if request.method == 'GET':
        custom_instructions = CustomInstructions.objects.filter(project=user_project).order_by('language__name')
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
        custom_instruction.project = user_project
        custom_instruction.save()

        # Log the action in the LogDiary
        LogDiary.objects.create(user = request.user, action = "Saved_Custom_Instructions", project = user_project)
        
        return render(request, 'xliff_manager/custom_instructions_confirmation.html', {'num_records': len(custom_instructions)})


def confirm_insertion_view(request, num_records):
    return render(request, 'xliff_manager/confirm_insertion.html', {'num_records': num_records})