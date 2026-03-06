from django.urls import path
from . import views
from .custom_logout import logout_view

app_name = 'accounts'

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
    path('profile/', views.ProfileView, name='profile'),
    path('change-password/', views.ChangePasswordView, name='change_password'),
    path('enable-2fa/', views.enable_2fa, name='enable_2fa'),
    path('login-2fa/', views.login_2fa, name='login_2fa'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
]
