from django.contrib import admin

from .models import Policy, PolicyAcknowledgment, PolicyCategory, PolicyReview


@admin.register(PolicyCategory)
class PolicyCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "status",
        "version",
        "effective_date",
        "created_at",
    )
    list_filter = ("status", "category")
    search_fields = ("title", "description")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"


@admin.register(PolicyReview)
class PolicyReviewAdmin(admin.ModelAdmin):
    list_display = ("policy", "reviewer", "review_date", "review_type")
    list_filter = ("review_type",)
    search_fields = ("policy__title",)
    readonly_fields = ("review_date", "created_at")


@admin.register(PolicyAcknowledgment)
class PolicyAcknowledgmentAdmin(admin.ModelAdmin):
    list_display = ("policy", "user", "acknowledged_at")
    list_filter = ("policy",)
    search_fields = ("policy__title", "user__email")
    readonly_fields = ("acknowledged_at",)
