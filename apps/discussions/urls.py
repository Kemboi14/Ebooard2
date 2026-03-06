from django.urls import path
from . import views

app_name = 'discussions'

urlpatterns = [
    # Forum URLs
    path('', views.ForumListView.as_view(), name='forum_list'),
    path('create/', views.ForumCreateView.as_view(), name='forum_create'),
    path('<uuid:pk>/', views.ForumDetailView.as_view(), name='forum_detail'),
    
    # Thread URLs
    path('threads/create/', views.ThreadCreateView.as_view(), name='thread_create'),
    path('threads/<uuid:pk>/', views.ThreadDetailView.as_view(), name='thread_detail'),
    
    # Post URLs
    path('posts/<uuid:pk>/create/', views.create_post, name='create_post'),
    path('posts/<uuid:pk>/edit/', views.edit_post, name='edit_post'),
    path('posts/<uuid:pk>/react/', views.PostReactionView.as_view(), name='post_reaction'),
    
    # Poll URLs
    path('polls/<uuid:pk>/create/', views.create_poll, name='create_poll'),
    path('polls/<uuid:pk>/vote/', views.vote_poll, name='vote_poll'),
    
    # Subscription URLs
    path('threads/<uuid:pk>/subscribe/', views.manage_subscription, name='manage_subscription'),
    
    # Tag URLs
    path('tags/', views.TagListView.as_view(), name='tag_list'),
    path('tags/create/', views.TagCreateView.as_view(), name='tag_create'),
    path('tags/<uuid:pk>/', views.TagDetailView.as_view(), name='tag_detail'),
    
    # Search URLs
    path('search/', views.search_discussions, name='search_discussions'),
    
    # Dashboard URL
    path('dashboard/', views.discussions_dashboard, name='dashboard'),
]
