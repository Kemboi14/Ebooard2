from django.urls import path
from . import views

app_name = 'voting'

urlpatterns = [
    path('', views.MotionListView.as_view(), name='motion_list'),
    path('motions/create/', views.CreateMotionView.as_view(), name='create_motion'),
    path('motions/<uuid:pk>/', views.MotionDetailView.as_view(), name='motion_detail'),
    path('motions/<uuid:pk>/vote/', views.cast_vote, name='cast_vote'),
    path('motions/<uuid:pk>/results/', views.vote_results, name='vote_results'),
    path('search/', views.motion_search, name='motion_search'),
    path('session/', views.manage_voting_session, name='manage_session'),
    path('dashboard/', views.voting_dashboard, name='voting_dashboard'),
]
