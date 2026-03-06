from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('', views.DocumentListView.as_view(), name='document_list'),
    path('upload/', views.UploadDocumentView.as_view(), name='upload_document'),
    path('<uuid:pk>/', views.DocumentDetailView.as_view(), name='document_detail'),
    path('<uuid:pk>/download/', views.download_document, name='download_document'),
    path('search/', views.document_search, name='document_search'),
    path('categories/', views.manage_categories, name='manage_categories'),
]
