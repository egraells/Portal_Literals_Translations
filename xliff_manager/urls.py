from django.urls import path
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('home/', views.home, name='home'),
    path('request_translation/', views.request_translation_view, name='request_translation'),
    path('request_translation?start_new=True', views.request_translation_view, name='start_new'),

    path('request_review/', views.request_review_view, name='request_review'),
    path('review_request/<int:request_id>/', views.do_review_view, name='do_request_review'),
    
    path('check_request_status', views.check_request_status_view, name='check_request_status'),
    path('my_pending_reviews', views.choose_review_view, name='choose_review_view'),

    path('diary_log', views.diary_log_view, name='diary_log'),
    path('custom_instructions', views.custom_instructions_view, name='custom_instructions'),

    path('download_file_confirmed/', views.download_file_confirmed, name='download_file_confirmed'),
    path('download_file/<str:type>/<str:id>/<path:file_to_download>/', views.download_file, name='download_file'),
    
    path('login/', LoginView.as_view(template_name='xliff_manager/login.html'), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'), 
    path('admin/', admin.site.urls),
    path('userpage', views.userpage, name='userpage'),
    
    path('confirm_insertion/<int:num_records>/', views.confirm_insertion_view, name='confirm_insertion'),
]