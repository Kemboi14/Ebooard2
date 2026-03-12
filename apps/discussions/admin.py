from django.contrib import admin

from .models import (
    DiscussionForum,
    DiscussionModeration,
    DiscussionPoll,
    DiscussionPost,
    DiscussionSubscription,
    DiscussionTag,
    DiscussionThread,
)


@admin.register(DiscussionForum)
class DiscussionForumAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "forum_type",
        "access_level",
        "is_active",
        "is_moderated",
        "created_at",
    )
    list_filter = ("forum_type", "access_level", "is_active", "is_moderated")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("order", "name")


@admin.register(DiscussionThread)
class DiscussionThreadAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "forum",
        "author",
        "status",
        "priority",
        "is_pinned",
        "is_locked",
        "view_count",
        "created_at",
    )
    list_filter = (
        "status",
        "priority",
        "is_pinned",
        "is_locked",
        "is_anonymous",
        "forum",
    )
    search_fields = (
        "title",
        "content",
        "author__email",
        "author__first_name",
        "author__last_name",
    )
    readonly_fields = ("created_at", "updated_at", "view_count", "last_activity")
    ordering = ("-created_at",)
    raw_id_fields = ("author", "forum")
    filter_horizontal = ("participants",)


@admin.register(DiscussionPost)
class DiscussionPostAdmin(admin.ModelAdmin):
    list_display = (
        "thread",
        "author",
        "post_type",
        "is_anonymous",
        "is_approved",
        "is_edited",
        "like_count",
        "created_at",
    )
    list_filter = (
        "post_type",
        "is_anonymous",
        "is_approved",
        "is_edited",
        "created_at",
    )
    search_fields = (
        "content",
        "author__email",
        "author__first_name",
        "author__last_name",
    )
    readonly_fields = ("created_at", "updated_at", "like_count", "dislike_count")
    ordering = ("-created_at",)
    raw_id_fields = ("author", "thread", "parent")


@admin.register(DiscussionTag)
class DiscussionTagAdmin(admin.ModelAdmin):
    list_display = ("name", "color", "usage_count", "created_at")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "usage_count")
    ordering = ("name",)


@admin.register(DiscussionPoll)
class DiscussionPollAdmin(admin.ModelAdmin):
    list_display = (
        "question",
        "thread",
        "created_by",
        "allow_multiple_choices",
        "is_anonymous",
        "ends_at",
        "created_at",
    )
    list_filter = ("allow_multiple_choices", "is_anonymous", "created_at")
    search_fields = ("question", "description", "thread__title")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    raw_id_fields = ("thread", "created_by")


@admin.register(DiscussionSubscription)
class DiscussionSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "thread", "subscription_type", "created_at")
    list_filter = ("subscription_type", "created_at")
    search_fields = ("user__email", "thread__title")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    raw_id_fields = ("user", "thread")


@admin.register(DiscussionModeration)
class DiscussionModerationAdmin(admin.ModelAdmin):
    list_display = ("moderator", "target_user", "action_type", "thread", "created_at")
    list_filter = ("action_type", "created_at")
    search_fields = ("moderator__email", "target_user__email", "reason")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
    raw_id_fields = ("moderator", "target_user", "thread", "post")
