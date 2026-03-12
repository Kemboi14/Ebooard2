from django.contrib import admin

from .models import (
    Risk,
    RiskAssessment,
    RiskCategory,
    RiskIncident,
    RiskMitigation,
    RiskMonitoring,
)


@admin.register(RiskCategory)
class RiskCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "category_type", "risk_count")
    list_filter = ("category_type",)
    search_fields = ("name", "description")

    @admin.display(description="Risks")
    def risk_count(self, obj):
        return obj.risks.count()


@admin.register(Risk)
class RiskAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "impact_level",
        "probability",
        "risk_score",
        "status",
        "risk_owner",
        "created_at",
    )
    list_filter = ("status", "impact_level", "probability", "category")
    search_fields = ("title", "description", "risk_owner__email")
    readonly_fields = ("risk_score", "created_at", "updated_at")
    date_hierarchy = "created_at"
    ordering = ("-risk_score", "-created_at")

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "description",
                    "category",
                    "risk_owner",
                    "assigned_to",
                    "status",
                )
            },
        ),
        (
            "Risk Scoring",
            {"fields": ("impact_level", "probability", "risk_score")},
        ),
        (
            "Dates",
            {
                "fields": (
                    "identified_date",
                    "target_resolution_date",
                    "actual_resolution_date",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(RiskAssessment)
class RiskAssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "risk",
        "assessed_by",
        "assessment_date",
        "impact_probability",
        "impact_severity",
        "priority_level",
    )
    list_filter = ("priority_level", "assessment_date")
    search_fields = ("risk__title", "assessed_by__email")
    date_hierarchy = "assessment_date"
    ordering = ("-assessment_date",)


@admin.register(RiskMitigation)
class RiskMitigationAdmin(admin.ModelAdmin):
    list_display = (
        "risk",
        "mitigation_type",
        "title",
        "status",
        "responsible_party",
        "target_completion_date",
    )
    list_filter = ("status", "mitigation_type")
    search_fields = ("risk__title", "title", "description")
    ordering = ("target_completion_date",)


@admin.register(RiskMonitoring)
class RiskMonitoringAdmin(admin.ModelAdmin):
    list_display = (
        "risk",
        "monitored_by",
        "monitoring_date",
        "monitoring_type",
        "current_status",
        "escalation_required",
    )
    list_filter = ("monitoring_type", "current_status", "escalation_required")
    search_fields = ("risk__title", "monitored_by__email", "actions_taken")
    date_hierarchy = "monitoring_date"
    ordering = ("-monitoring_date",)


@admin.register(RiskIncident)
class RiskIncidentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "risk",
        "severity",
        "status",
        "reported_by",
        "incident_date",
    )
    list_filter = ("severity", "status", "incident_date")
    search_fields = ("title", "description", "risk__title", "reported_by__email")
    date_hierarchy = "incident_date"
    ordering = ("-incident_date",)
