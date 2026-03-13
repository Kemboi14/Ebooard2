import uuid

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils import timezone

User = get_user_model()


class DiscussionForum(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    """Discussion forums for organizing board communications"""

    FORUM_TYPES = [
        ("general", "General Discussion"),
        ("strategy", "Strategy & Planning"),
        ("governance", "Governance & Compliance"),
        ("finance", "Financial Matters"),
        ("operations", "Operations & Performance"),
        ("risk", "Risk Management"),
        ("policy", "Policy Development"),
        ("confidential", "Confidential Matters"),
        ("committee", "Committee Specific"),
        ("emergency", "Emergency Communications"),
    ]

    ACCESS_LEVELS = [
        ("public", "Public - All Board Members"),
        ("restricted", "Restricted - Selected Members"),
        ("confidential", "Confidential - Board Leadership"),
        ("private", "Private - Invite Only"),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    forum_type = models.CharField(max_length=20, choices=FORUM_TYPES, default="general")
    access_level = models.CharField(
        max_length=20, choices=ACCESS_LEVELS, default="public"
    )

    # Forum settings
    is_active = models.BooleanField(default=True)
    is_moderated = models.BooleanField(default=True)
    allow_attachments = models.BooleanField(default=True)
    allow_polls = models.BooleanField(default=True)

    # Ordering and display
    order = models.PositiveIntegerField(default=0)
    icon = models.CharField(
        max_length=50, blank=True, help_text="Font Awesome icon class"
    )

    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_forums",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "Discussion Forums"
        verbose_name = "Discussion Forum"

    def __str__(self):
        return f"{self.name} ({self.get_forum_type_display()})"

    def get_absolute_url(self):
        return reverse("discussions:forum_detail", kwargs={"pk": self.pk})

    @property
    def thread_count(self):
        return self.threads.count()

    @property
    def post_count(self):
        return DiscussionPost.objects.filter(thread__forum=self).count()

    @property
    def latest_activity(self):
        latest_post = (
            DiscussionPost.objects.filter(thread__forum=self)
            .order_by("-created_at")
            .first()
        )
        return latest_post.created_at if latest_post else None


class DiscussionThread(models.Model):
    """Discussion threads within forums"""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("locked", "Locked"),
        ("pinned", "Pinned"),
        ("archived", "Archived"),
        ("deleted", "Deleted"),
    ]

    PRIORITY_LEVELS = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("urgent", "Urgent"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    forum = models.ForeignKey(
        DiscussionForum, on_delete=models.CASCADE, related_name="threads"
    )

    # Thread details
    title = models.CharField(max_length=300)
    content = models.TextField()

    # Thread metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    priority = models.CharField(
        max_length=10, choices=PRIORITY_LEVELS, default="normal"
    )

    # Author and participants
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authored_threads",
    )
    participants = models.ManyToManyField(
        User, blank=True, related_name="participating_threads"
    )

    # Related content (optional)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.SET_NULL, null=True, blank=True
    )
    object_id = models.CharField(max_length=50, null=True, blank=True)
    related_object = GenericForeignKey("content_type", "object_id")

    # Thread settings
    is_locked = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    is_anonymous = models.BooleanField(default=False, help_text="Hide author identity")

    # Tracking
    view_count = models.PositiveIntegerField(default=0)
    last_activity = models.DateTimeField(auto_now=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "-last_activity"]
        indexes = [
            models.Index(fields=["forum", "status", "-last_activity"]),
            models.Index(fields=["author", "-created_at"]),
            models.Index(fields=["priority", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.forum.name})"

    def get_absolute_url(self):
        return reverse("discussions:thread_detail", kwargs={"pk": self.pk})

    @property
    def post_count(self):
        return self.posts.count()

    @property
    def reply_count(self):
        return self.posts.count() - 1  # Exclude the original post

    @property
    def latest_post(self):
        return self.posts.order_by("-created_at").first()

    @property
    def participant_count(self):
        return self.participants.count()

    def increment_views(self):
        self.view_count += 1
        self.save(update_fields=["view_count"])


class DiscussionPost(models.Model):
    """Individual posts within discussion threads"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    POST_TYPES = [
        ("original", "Original Post"),
        ("reply", "Reply"),
        ("moderation", "Moderation Note"),
        ("system", "System Message"),
    ]

    thread = models.ForeignKey(
        DiscussionThread, on_delete=models.CASCADE, related_name="posts"
    )

    # Post content
    content = models.TextField()
    post_type = models.CharField(max_length=20, choices=POST_TYPES, default="reply")

    # Author information
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discussion_posts",
    )
    is_anonymous = models.BooleanField(default=False)

    # Post metadata
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    order = models.PositiveIntegerField(default=0)

    # Moderation
    is_approved = models.BooleanField(default=True)
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    edited_reason = models.CharField(max_length=200, blank=True)

    # Reactions and engagement
    like_count = models.PositiveIntegerField(default=0)
    dislike_count = models.PositiveIntegerField(default=0)

    # Attachments
    attachments = models.JSONField(
        null=True, blank=True, help_text="List of attached files"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "created_at"]
        indexes = [
            models.Index(fields=["thread", "created_at"]),
            models.Index(fields=["author", "-created_at"]),
            models.Index(fields=["parent", "order"]),
        ]

    def __str__(self):
        content_preview = (
            self.content[:50] + "..." if len(self.content) > 50 else self.content
        )
        return f"Post in {self.thread.title}: {content_preview}"

    def get_absolute_url(self):
        return f"{self.thread.get_absolute_url()}#post-{self.pk}"

    @property
    def is_original(self):
        return self.post_type == "original"

    @property
    def display_name(self):
        if self.is_anonymous:
            return "Anonymous"
        return self.author.get_full_name() if self.author else "Unknown"


class PostReaction(models.Model):
    """User reactions to discussion posts"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    REACTION_TYPES = [
        ("like", "Like"),
        ("dislike", "Dislike"),
        ("love", "Love"),
        ("laugh", "Laugh"),
        ("angry", "Angry"),
        ("sad", "Sad"),
        ("wow", "Wow"),
    ]

    post = models.ForeignKey(
        DiscussionPost, on_delete=models.CASCADE, related_name="reactions"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="post_reactions"
    )
    reaction_type = models.CharField(max_length=10, choices=REACTION_TYPES)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["post", "user"]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.get_full_name()} {self.get_reaction_type_display()} post {self.post.pk}"


class DiscussionPoll(models.Model):
    """Polls within discussion threads"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    thread = models.ForeignKey(
        DiscussionThread, on_delete=models.CASCADE, related_name="polls"
    )
    question = models.CharField(max_length=300)
    description = models.TextField(blank=True)

    # Poll settings
    allow_multiple_choices = models.BooleanField(default=False)
    is_anonymous = models.BooleanField(default=False)
    ends_at = models.DateTimeField(null=True, blank=True)

    # Author
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Poll: {self.question}"

    @property
    def is_active(self):
        if self.ends_at:
            return timezone.now() < self.ends_at
        return True

    @property
    def total_votes(self):
        return PollVote.objects.filter(poll=self).count()


class PollOption(models.Model):
    """Options for discussion polls"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    poll = models.ForeignKey(
        DiscussionPoll, on_delete=models.CASCADE, related_name="options"
    )
    text = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"{self.text} (Poll: {self.poll.question})"

    @property
    def vote_count(self):
        return PollVote.objects.filter(option=self).count()

    @property
    def vote_percentage(self):
        total_votes = self.poll.total_votes
        if total_votes == 0:
            return 0
        return (self.vote_count / total_votes) * 100


class PollVote(models.Model):
    """Votes in discussion polls"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    poll = models.ForeignKey(DiscussionPoll, on_delete=models.CASCADE)
    option = models.ForeignKey(PollOption, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["poll", "user"]

    def __str__(self):
        return f"{self.user.get_full_name()} voted for {self.option.text}"


class DiscussionSubscription(models.Model):
    """User subscriptions to discussion threads"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    SUBSCRIPTION_TYPES = [
        ("all", "All Posts"),
        ("mentions", "Mentions Only"),
        ("none", "No Notifications"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="discussion_subscriptions"
    )
    thread = models.ForeignKey(
        DiscussionThread, on_delete=models.CASCADE, related_name="subscriptions"
    )
    subscription_type = models.CharField(
        max_length=20, choices=SUBSCRIPTION_TYPES, default="all"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "thread"]

    def __str__(self):
        return f"{self.user.get_full_name()} subscribed to {self.thread.title}"


class DiscussionModeration(models.Model):
    """Moderation actions and logs"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ACTION_TYPES = [
        ("lock_thread", "Lock Thread"),
        ("unlock_thread", "Unlock Thread"),
        ("pin_thread", "Pin Thread"),
        ("unpin_thread", "Unpin Thread"),
        ("delete_post", "Delete Post"),
        ("edit_post", "Edit Post"),
        ("warn_user", "Warn User"),
        ("suspend_user", "Suspend User"),
    ]

    thread = models.ForeignKey(
        DiscussionThread,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="moderations",
    )
    post = models.ForeignKey(
        DiscussionPost,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="moderations",
    )

    moderator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_actions",
    )
    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_targets",
    )

    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    reason = models.TextField()

    # Previous content (for edits/deletions)
    previous_content = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_type_display()} by {self.moderator.get_full_name() if self.moderator else 'System'}"


class DiscussionTag(models.Model):
    """Tags for categorizing discussions"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(
        max_length=7, default="#007bff", help_text="Hex color code"
    )

    # Usage tracking
    usage_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ThreadTag(models.Model):
    """Many-to-many relationship between threads and tags"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    thread = models.ForeignKey(
        DiscussionThread, on_delete=models.CASCADE, related_name="thread_tags"
    )
    tag = models.ForeignKey(
        DiscussionTag, on_delete=models.CASCADE, related_name="tagged_threads"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["thread", "tag"]

    def __str__(self):
        return f"{self.thread.title} tagged with {self.tag.name}"
