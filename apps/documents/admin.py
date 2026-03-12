from django.contrib import admin

from .models import (
    Document,
    DocumentAccess,
    DocumentActivity,
    DocumentCategory,
    DocumentComment,
    DocumentShare,
    DocumentTag,
)


@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "created_at")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(DocumentTag)
class DocumentTagAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "uploaded_by",
        "status",
        "access_level",
        "created_at",
    )
    list_filter = ("status", "access_level", "category", "created_at")
    search_fields = ("title", "description", "uploaded_by__email")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("uploaded_by", "category")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


@admin.register(DocumentAccess)
class DocumentAccessAdmin(admin.ModelAdmin):
    list_display = ("document", "user", "permission", "granted_by", "granted_at")
    list_filter = ("permission", "granted_at")
    search_fields = ("document__title", "user__email")
    readonly_fields = ("granted_at",)
    raw_id_fields = ("document", "user", "granted_by")
    ordering = ("-granted_at",)


@admin.register(DocumentActivity)
class DocumentActivityAdmin(admin.ModelAdmin):
    list_display = ("document", "user", "activity_type", "created_at")
    list_filter = ("activity_type", "created_at")
    search_fields = ("document__title", "user__email", "description")
    readonly_fields = ("created_at",)
    raw_id_fields = ("document", "user")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


@admin.register(DocumentShare)
class DocumentShareAdmin(admin.ModelAdmin):
    list_display = (
        "document",
        "shared_by",
        "share_token",
        "can_download",
        "can_edit",
        "created_at",
        "expires_at",
    )
    list_filter = ("can_download", "can_edit", "created_at")
    search_fields = ("document__title", "shared_by__email", "share_token")
    readonly_fields = ("created_at", "share_token", "download_count")
    raw_id_fields = ("document", "shared_by")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


@admin.register(DocumentComment)
class DocumentCommentAdmin(admin.ModelAdmin):
    list_display = ("document", "user", "is_resolved", "page_number", "created_at")
    list_filter = ("is_resolved", "created_at")
    search_fields = ("document__title", "user__email", "content")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("document", "user", "parent", "resolved_by")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
