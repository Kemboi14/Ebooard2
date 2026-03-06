from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # Notification URLs
    path('', views.NotificationListView.as_view(), name='notification_list'),
    path('center/', views.notification_center, name='notification_center'),
    path('<uuid:pk>/', views.NotificationDetailView.as_view(), name='notification_detail'),
    path('create/', views.NotificationCreateView.as_view(), name='notification_create'),
    
    # Notification Actions
    path('<uuid:pk>/mark-read/', views.mark_notification_read, name='mark_read'),
    path('<uuid:pk>/mark-unread/', views.mark_notification_unread, name='mark_unread'),
    path('<uuid:pk>/delete/', views.delete_notification, name='delete'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    
    # Preferences
    path('preferences/', views.notification_preferences, name='preferences'),
    
    # Quick Notification
    path('quick/', views.quick_notification, name='quick_notification'),
    
    # Templates (admin only)
    path('templates/', views.NotificationTemplateListView.as_view(), name='template_list'),
    path('templates/create/', views.NotificationTemplateCreateView.as_view(), name='template_create'),
    
    # Batch Notifications
    path('batch/', views.NotificationBatchCreateView.as_view(), name='batch_create'),
    
    # Channels (admin only)
    path('channels/', views.NotificationChannelListView.as_view(), name='channel_list'),
    path('channels/create/', views.NotificationChannelCreateView.as_view(), name='channel_create'),
    
    # API endpoints
    path('stats/', views.notification_stats, name='stats'),
    path('test/', views.send_test_notification, name='test_notification'),
]
