from django.contrib import admin

from .models import (
    CalibrationSession,
    Evaluation,
    EvaluationAnalytics,
    EvaluationAnswer,
    EvaluationComment,
    EvaluationCycle,
    EvaluationFramework,
    EvaluationQuestion,
    EvaluationTemplate,
)


@admin.register(EvaluationFramework)
class EvaluationFrameworkAdmin(admin.ModelAdmin):
    list_display = ("name", "framework_type", "created_at")
    list_filter = ("framework_type",)
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("name",)


@admin.register(EvaluationTemplate)
class EvaluationTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "evaluation_type",
        "framework",
        "is_active",
        "is_public",
        "question_count",
        "created_at",
    )
    list_filter = ("evaluation_type", "is_active", "is_public", "framework")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at", "usage_count", "last_used")
    ordering = ("name",)

    @admin.display(description="Questions")
    def question_count(self, obj):
        return obj.questions.count()


@admin.register(EvaluationQuestion)
class EvaluationQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "text",
        "template",
        "question_type",
        "category",
        "order",
        "is_required",
        "weight",
    )
    list_filter = ("question_type", "is_required", "template")
    search_fields = ("text", "template__name", "category")
    ordering = ("template", "order")
    raw_id_fields = ("template",)


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = (
        "evaluation_period",
        "template",
        "evaluator",
        "evaluatee",
        "status",
        "percentage_score",
        "start_date",
        "end_date",
        "created_at",
    )
    list_filter = ("status", "template", "created_at")
    search_fields = (
        "evaluation_period",
        "evaluator__email",
        "evaluatee__email",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "submitted_at",
        "reviewed_at",
        "approved_at",
        "percentage_score",
        "total_score",
        "max_possible_score",
    )
    raw_id_fields = ("template", "evaluator", "evaluatee", "reviewed_by", "approved_by")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    fieldsets = (
        (
            "Core",
            {
                "fields": (
                    "id",
                    "template",
                    "evaluation_period",
                    "status",
                    "evaluator",
                    "evaluatee",
                ),
            },
        ),
        (
            "Dates",
            {
                "fields": ("start_date", "end_date", "submitted_at"),
            },
        ),
        (
            "Scores",
            {
                "fields": ("total_score", "max_possible_score", "percentage_score"),
            },
        ),
        (
            "Review",
            {
                "fields": (
                    "reviewed_by",
                    "reviewed_at",
                    "review_comments",
                    "approved_by",
                    "approved_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Calibration",
            {
                "fields": ("requires_calibration", "calibration_completed"),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(EvaluationAnswer)
class EvaluationAnswerAdmin(admin.ModelAdmin):
    list_display = ("evaluation", "question", "score", "choice_answer", "created_at")
    list_filter = ("created_at",)
    search_fields = ("evaluation__evaluation_period", "question__text")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("evaluation", "question")
    ordering = ("-created_at",)


@admin.register(EvaluationComment)
class EvaluationCommentAdmin(admin.ModelAdmin):
    list_display = ("evaluation", "author", "comment_type", "is_public", "created_at")
    list_filter = ("comment_type", "is_public", "created_at")
    search_fields = ("evaluation__evaluation_period", "author__email", "text")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("evaluation", "author")
    ordering = ("-created_at",)


@admin.register(EvaluationCycle)
class EvaluationCycleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "start_date",
        "end_date",
        "is_active",
        "is_completed",
        "evaluation_count",
        "created_at",
    )
    list_filter = ("is_active", "is_completed")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("participants",)
    raw_id_fields = ("created_by", "template")
    ordering = ("-start_date",)

    @admin.display(description="Evaluations")
    def evaluation_count(self, obj):
        return obj.template.evaluations.count() if obj.template else 0


@admin.register(CalibrationSession)
class CalibrationSessionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "session_type",
        "status",
        "scheduled_date",
        "facilitator",
        "created_at",
    )
    list_filter = ("status", "session_type", "scheduled_date")
    search_fields = ("name", "facilitator__email")
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("participants",)
    raw_id_fields = ("facilitator", "created_by")
    ordering = ("-scheduled_date",)


@admin.register(EvaluationAnalytics)
class EvaluationAnalyticsAdmin(admin.ModelAdmin):
    list_display = (
        "evaluation",
        "mean_score",
        "median_score",
        "percentile_rank",
        "generated_at",
    )
    list_filter = ("generated_at",)
    search_fields = ("evaluation__evaluation_period",)
    readonly_fields = ("generated_at", "last_updated")
    raw_id_fields = ("evaluation",)
    ordering = ("-generated_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
