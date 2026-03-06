from django.urls import path
from . import views

app_name = 'meetings'

urlpatterns = [
    path('', views.MeetingListView.as_view(), name='meeting_list'),
    path('create/', views.CreateMeetingView.as_view(), name='create_meeting'),
    path('<uuid:pk>/', views.MeetingDetailView.as_view(), name='meeting_detail'),
    path('<uuid:pk>/update/', views.UpdateMeetingView.as_view(), name='update_meeting'),
    path('<uuid:pk>/agenda/', views.manage_agenda, name='manage_agenda'),
    path('<uuid:pk>/minutes/', views.manage_minutes, name='manage_minutes'),
    path('<uuid:pk>/attendance/', views.manage_attendance, name='manage_attendance'),
    path('search/', views.meeting_search, name='meeting_search'),
]
