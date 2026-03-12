from django.contrib import admin

from .models import Motion, Vote, VoteOption, VoteResult, VotingSession


@admin.register(Motion)
class MotionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "status",
        "voting_type",
        "proposed_by",
        "voting_deadline",
        "created_at",
    )
    list_filter = ("status", "category", "voting_type")
    search_fields = ("title", "description", "reference_number")
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "voting_started_at",
        "voting_ended_at",
    )
    raw_id_fields = ("proposed_by", "seconded_by", "meeting")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "id",
                    "title",
                    "description",
                    "background",
                    "category",
                    "reference_number",
                    "meeting",
                )
            },
        ),
        (
            "Voting Configuration",
            {
                "fields": (
                    "voting_type",
                    "required_votes",
                    "voting_deadline",
                    "allow_anonymous",
                )
            },
        ),
        (
            "Status & People",
            {
                "fields": (
                    "status",
                    "proposed_by",
                    "seconded_by",
                )
            },
        ),
        (
            "Outcome",
            {"fields": ("result_notes",)},
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": (
                    "created_at",
                    "updated_at",
                    "voting_started_at",
                    "voting_ended_at",
                    "tabled_at",
                ),
            },
        ),
    )


@admin.register(VotingSession)
class VotingSessionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "status",
        "start_time",
        "end_time",
        "created_by",
        "motions_count",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("title", "description")
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("created_by", "meeting")
    filter_horizontal = ("motions", "eligible_voters")
    ordering = ("-start_time",)

    @admin.display(description="Motions")
    def motions_count(self, obj):
        return obj.motions.count()


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = (
        "motion",
        "voter_display",
        "choice",
        "is_anonymous",
        "cast_at",
    )
    list_filter = ("choice", "is_anonymous", "cast_at")
    search_fields = ("motion__title",)
    readonly_fields = ("id", "cast_at", "ip_address", "user_agent")
    raw_id_fields = ("motion", "voter", "vote_option")
    ordering = ("-cast_at",)

    @admin.display(description="Voter")
    def voter_display(self, obj):
        if obj.is_anonymous:
            return "Anonymous"
        return obj.voter.get_full_name() if obj.voter else "—"


@admin.register(VoteOption)
class VoteOptionAdmin(admin.ModelAdmin):
    list_display = ("motion", "text", "order", "vote_count")
    list_filter = ()
    search_fields = ("motion__title", "text")
    readonly_fields = ("id",)
    raw_id_fields = ("motion",)
    ordering = ("motion", "order")

    @admin.display(description="Votes")
    def vote_count(self, obj):
        return obj.votes.count()


@admin.register(VoteResult)
class VoteResultAdmin(admin.ModelAdmin):
    list_display = (
        "motion",
        "passed",
        "total_votes",
        "yes_votes",
        "no_votes",
        "abstain_votes",
        "certified_by",
        "certified_at",
    )
    list_filter = ("passed", "voting_type")
    search_fields = ("motion__title",)
    readonly_fields = ("id", "certified_at", "updated_at")
    raw_id_fields = ("motion", "certified_by")
    ordering = ("-certified_at",)
