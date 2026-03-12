from django.urls import path

from . import views

app_name = "evaluation"

urlpatterns = [
    # Evaluation URLs
    path("", views.EvaluationListView.as_view(), name="evaluation_list"),
    path("dashboard/", views.evaluation_dashboard, name="evaluation_dashboard"),
    path("create/", views.EvaluationCreateView.as_view(), name="evaluation_create"),
    path("<uuid:pk>/", views.EvaluationDetailView.as_view(), name="evaluation_detail"),
    path(
        "<uuid:pk>/update/",
        views.EvaluationUpdateView.as_view(),
        name="evaluation_update",
    ),
    path("<uuid:pk>/take/", views.take_evaluation, name="take_evaluation"),
    path("<uuid:pk>/submit/", views.submit_evaluation, name="submit_evaluation"),
    path("<uuid:pk>/review/", views.review_evaluation, name="review_evaluation"),
    # Template URLs
    path("templates/", views.TemplateListView.as_view(), name="template_list"),
    path(
        "templates/create/", views.TemplateCreateView.as_view(), name="template_create"
    ),
    path(
        "templates/<uuid:pk>/",
        views.TemplateDetailView.as_view(),
        name="template_detail",
    ),
    path("templates/<uuid:pk>/add-question/", views.add_question, name="add_question"),
    path(
        "templates/populate-professional/",
        views.populate_professional_templates,
        name="populate_professional_templates",
    ),
    # Cycle URLs
    path("cycles/", views.CycleListView.as_view(), name="cycle_list"),
    path("cycles/create/", views.CycleCreateView.as_view(), name="cycle_create"),
    path("cycles/<uuid:pk>/", views.CycleDetailView.as_view(), name="cycle_detail"),
    path("cycles/<uuid:pk>/edit/", views.CycleUpdateView.as_view(), name="cycle_edit"),
]
