from django.urls import path
from . import views

app_name = 'policy'

urlpatterns = [
    # Policy URLs
    path('', views.PolicyListView.as_view(), name='policy_list'),
    path('create/', views.PolicyCreateView.as_view(), name='policy_create'),
    path('<uuid:pk>/', views.PolicyDetailView.as_view(), name='policy_detail'),
    path('<uuid:pk>/update/', views.PolicyUpdateView.as_view(), name='policy_update'),
    path('<uuid:pk>/create-version/', views.create_policy_version, name='create_version'),
    path('<uuid:pk>/acknowledge/', views.acknowledge_policy, name='acknowledge_policy'),
    
    # Category URLs
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/update/', views.CategoryUpdateView.as_view(), name='category_update'),
    
    # Review URLs
    path('<uuid:pk>/review/create/', views.ReviewCreateView.as_view(), name='create_review'),
    
    # Dashboard
    path('dashboard/', views.policy_dashboard, name='dashboard'),
    
    # Policy Expiry Monitor
    path('expiry-monitors/', views.PolicyExpiryMonitorListView.as_view(), name='policy_expiry_monitors'),
    path('expiry-monitors/<uuid:pk>/', views.PolicyExpiryMonitorDetailView.as_view(), name='policy_expiry_monitor_detail'),
    path('expiry-monitors/create/', views.PolicyExpiryMonitorCreateView.as_view(), name='policy_expiry_monitor_create'),
    path('expiry-monitors/<uuid:pk>/update/', views.PolicyExpiryMonitorUpdateView.as_view(), name='policy_expiry_monitor_update'),
]
