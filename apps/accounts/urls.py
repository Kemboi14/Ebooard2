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
    
    # SSO Providers
    path('sso-providers/', views.SSOProviderListView.as_view(), name='sso_providers'),
    path('sso-providers/<uuid:pk>/', views.SSOProviderDetailView.as_view(), name='sso_provider_detail'),
    path('sso-providers/create/', views.SSOProviderCreateView.as_view(), name='sso_provider_create'),
    
    # Session Management
    path('sessions/', views.UserSessionListView.as_view(), name='user_sessions'),
    path('sessions/<uuid:pk>/revoke/', views.revoke_session, name='revoke_session'),
    path('sessions/revoke-all/', views.revoke_all_other_sessions, name='revoke_all_sessions'),
    
    # Encryption Keys
    path('encryption-keys/', views.EncryptionKeyListView.as_view(), name='encryption_keys'),
    path('encryption-keys/create/', views.EncryptionKeyCreateView.as_view(), name='encryption_key_create'),
    path('encryption-keys/<uuid:pk>/rotate/', views.rotate_encryption_key, name='rotate_encryption_key'),
    
    # Multi-Language Support
    path('languages/', views.LanguageListView.as_view(), name='languages'),
    path('translations/', views.TranslationListView.as_view(), name='translations'),
    path('translations/create/', views.TranslationCreateView.as_view(), name='translation_create'),
    path('translations/<uuid:pk>/update/', views.TranslationUpdateView.as_view(), name='translation_update'),
    
    # Committees
    path('committees/', views.CommitteeListView.as_view(), name='committees'),
    path('committees/<uuid:pk>/', views.CommitteeDetailView.as_view(), name='committee_detail'),
    path('committees/create/', views.CommitteeCreateView.as_view(), name='committee_create'),
    path('committees/<uuid:pk>/update/', views.CommitteeUpdateView.as_view(), name='committee_update'),
    
    # Committee Memberships
    path('committee-memberships/', views.CommitteeMembershipListView.as_view(), name='committee_memberships'),
    path('committee-memberships/create/', views.CommitteeMembershipCreateView.as_view(), name='committee_membership_create'),
    path('committee-memberships/<uuid:pk>/update/', views.CommitteeMembershipUpdateView.as_view(), name='committee_membership_update'),
    
    # Bookmarks
    path('bookmarks/', views.BookmarkListView.as_view(), name='bookmarks'),
    path('bookmarks/create/', views.BookmarkCreateView.as_view(), name='bookmark_create'),
    path('bookmarks/<uuid:pk>/update/', views.BookmarkUpdateView.as_view(), name='bookmark_update'),
    path('bookmarks/<uuid:pk>/delete/', views.BookmarkDeleteView.as_view(), name='bookmark_delete'),
    
    # Field Edit Permissions
    path('field-permissions/', views.FieldEditPermissionListView.as_view(), name='field_permissions'),
    path('field-permissions/create/', views.FieldEditPermissionCreateView.as_view(), name='field_permission_create'),
    path('field-permissions/<uuid:pk>/update/', views.FieldEditPermissionUpdateView.as_view(), name='field_permission_update'),
]
