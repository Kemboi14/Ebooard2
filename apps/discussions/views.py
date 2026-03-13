from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from apps.accounts.models import User

from .forms import (
    DiscussionForumForm,
    DiscussionPollForm,
    DiscussionPostForm,
    DiscussionSearchForm,
    DiscussionSubscriptionForm,
    DiscussionTagForm,
    DiscussionThreadForm,
    PostEditForm,
)
from .models import (
    DiscussionForum,
    DiscussionPoll,
    DiscussionPost,
    DiscussionSubscription,
    DiscussionTag,
    DiscussionThread,
    PollOption,
    PollVote,
    PostReaction,
    ThreadTag,
)


class ForumListView(LoginRequiredMixin, ListView):
    """List all discussion forums"""

    model = DiscussionForum
    template_name = "discussions/forum_list.html"
    context_object_name = "forums"

    def get_queryset(self):
        user = self.request.user
        if user.role in ["company_secretary", "it_administrator"]:
            return DiscussionForum.objects.all().order_by("order", "name")
        else:
            return DiscussionForum.objects.filter(
                access_level="public", is_active=True
            ).order_by("order", "name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        forums = self.get_queryset()

        context["total_threads"] = DiscussionThread.objects.filter(
            forum__in=forums
        ).count()
        context["total_posts"] = DiscussionPost.objects.filter(
            thread__forum__in=forums
        ).count()
        context["active_polls"] = DiscussionPoll.objects.filter(
            thread__forum__in=forums,
            ends_at__gt=timezone.now(),
        ).count()
        context["recent_threads"] = (
            DiscussionThread.objects.filter(forum__in=forums)
            .select_related("author", "forum")
            .order_by("-last_activity")[:10]
        )
        return context


class ForumDetailView(LoginRequiredMixin, DetailView):
    """View forum details and threads"""

    model = DiscussionForum
    template_name = "discussions/forum_detail.html"
    context_object_name = "forum"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        forum = self.object

        # Get threads for this forum
        threads = (
            forum.threads.select_related("author")
            .prefetch_related("tags")
            .order_by("-is_pinned", "-last_activity")
        )

        # Apply filters
        search = self.request.GET.get("search")
        if search:
            threads = threads.filter(
                Q(title__icontains=search) | Q(content__icontains=search)
            )

        # Pagination
        paginator = Paginator(threads, 20)
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context["page_obj"] = page_obj
        context["threads"] = page_obj
        context["search_form"] = DiscussionSearchForm(self.request.GET)

        return context


class ThreadDetailView(LoginRequiredMixin, DetailView):
    """View discussion thread and posts"""

    model = DiscussionThread
    template_name = "discussions/thread_detail.html"
    context_object_name = "thread"

    def get_object(self):
        obj = super().get_object()
        # Increment view count
        obj.increment_views()
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        thread = self.object

        # Get posts with replies
        posts = thread.posts.select_related("author").order_by("order", "created_at")
        context["posts"] = posts

        # Get polls
        context["polls"] = thread.polls.prefetch_related("options").all()

        # Check if user is subscribed
        if self.request.user.is_authenticated:
            subscription, created = DiscussionSubscription.objects.get_or_create(
                user=self.request.user,
                thread=thread,
                defaults={"subscription_type": "all"},
            )
            context["subscription"] = subscription
            context["subscription_form"] = DiscussionSubscriptionForm(
                instance=subscription
            )

        # Forms for new content
        if not thread.is_locked:
            context["post_form"] = DiscussionPostForm(thread=thread)
            context["poll_form"] = DiscussionPollForm()

        return context


class ThreadCreateView(LoginRequiredMixin, CreateView):
    """Create a new discussion thread — open to all authenticated board members"""

    model = DiscussionThread
    form_class = DiscussionThreadForm
    template_name = "discussions/thread_form.html"
    success_url = reverse_lazy("discussions:forum_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        # Pre-select the forum if passed as a query param from forum_detail
        forum_pk = self.request.GET.get("forum")
        if forum_pk:
            try:
                initial["forum"] = DiscussionForum.objects.get(pk=forum_pk)
            except (DiscussionForum.DoesNotExist, ValueError):
                pass
        return initial

    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.save()

        # Create the original post from the thread content
        DiscussionPost.objects.create(
            thread=form.instance,
            author=self.request.user,
            content=form.cleaned_data["content"],
            post_type="original",
            order=0,
        )

        # Auto-subscribe the author
        form.instance.participants.add(self.request.user)
        DiscussionSubscription.objects.get_or_create(
            user=self.request.user,
            thread=form.instance,
            defaults={"subscription_type": "all"},
        )

        messages.success(
            self.request, f"Thread '{form.instance.title}' created successfully!"
        )
        return redirect("discussions:thread_detail", pk=form.instance.pk)


class PostReactionView(LoginRequiredMixin, View):
    """Handle post reactions"""

    def post(self, request, pk):
        post = get_object_or_404(DiscussionPost, pk=pk)
        reaction_type = request.POST.get("reaction_type")

        if reaction_type not in [choice[0] for choice in PostReaction.REACTION_TYPES]:
            return JsonResponse({"error": "Invalid reaction type"}, status=400)

        # Toggle reaction
        existing_reaction = PostReaction.objects.filter(
            post=post, user=request.user, reaction_type=reaction_type
        ).first()

        if existing_reaction:
            existing_reaction.delete()
            action = "removed"
        else:
            # Remove any existing reaction from this user on this post
            PostReaction.objects.filter(post=post, user=request.user).delete()

            # Add new reaction
            PostReaction.objects.create(
                post=post, user=request.user, reaction_type=reaction_type
            )
            action = "added"

        # Update reaction counts
        post.like_count = post.reactions.filter(reaction_type="like").count()
        post.dislike_count = post.reactions.filter(reaction_type="dislike").count()
        post.save(update_fields=["like_count", "dislike_count"])

        return JsonResponse(
            {
                "action": action,
                "like_count": post.like_count,
                "dislike_count": post.dislike_count,
            }
        )


@login_required
def create_post(request, pk):
    """Create a new post in a thread"""
    thread = get_object_or_404(DiscussionThread, pk=pk)

    if thread.is_locked:
        messages.error(request, "This thread is locked and cannot accept new posts.")
        return redirect("discussions:thread_detail", pk=pk)

    if request.method == "POST":
        form = DiscussionPostForm(request.POST, thread=thread)
        if form.is_valid():
            post = form.save(commit=False)
            post.thread = thread
            post.author = request.user
            post.post_type = "reply"

            # Set order
            last_order = (
                thread.posts.filter(post_type="reply").order_by("-order").first()
            )
            post.order = (last_order.order + 1) if last_order else 1

            post.save()

            # Update thread activity
            thread.last_activity = timezone.now()
            thread.participants.add(request.user)
            thread.save()

            messages.success(request, "Reply posted successfully!")
            return redirect("discussions:thread_detail", pk=pk)
    else:
        form = DiscussionPostForm(thread=thread)

    return render(
        request, "discussions/create_post.html", {"form": form, "thread": thread}
    )


@login_required
def edit_post(request, pk):
    """Edit a discussion post"""
    post = get_object_or_404(DiscussionPost, pk=pk)

    # Check permissions
    if post.author != request.user and request.user.role not in [
        "company_secretary",
        "it_administrator",
    ]:
        messages.error(request, "You don't have permission to edit this post.")
        return redirect("discussions:thread_detail", pk=post.thread.pk)

    if request.method == "POST":
        form = PostEditForm(request.POST, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, "Post updated successfully!")
            return redirect("discussions:thread_detail", pk=post.thread.pk)
    else:
        form = PostEditForm(instance=post)

    return render(
        request,
        "discussions/edit_post.html",
        {"form": form, "post": post, "thread": post.thread},
    )


@login_required
def create_poll(request, pk):
    """Create a poll in a thread"""
    thread = get_object_or_404(DiscussionThread, pk=pk)

    if not thread.forum.allow_polls:
        messages.error(request, "Polls are not allowed in this forum.")
        return redirect("discussions:thread_detail", pk=pk)

    if request.method == "POST":
        form = DiscussionPollForm(request.POST)
        if form.is_valid():
            poll = form.save(commit=False)
            poll.thread = thread
            poll.created_by = request.user
            poll.save()

            messages.success(request, "Poll created successfully!")
            return redirect("discussions:thread_detail", pk=pk)
    else:
        form = DiscussionPollForm()

    return render(
        request, "discussions/create_poll.html", {"form": form, "thread": thread}
    )


@login_required
def vote_poll(request, pk):
    """Vote in a poll"""
    poll = get_object_or_404(DiscussionPoll, pk=pk)

    if not poll.is_active:
        messages.error(request, "This poll is no longer active.")
        return redirect("discussions:thread_detail", pk=poll.thread.pk)

    if request.method == "POST":
        form = PollVoteForm(poll, request.POST)
        if form.is_valid():
            # Remove existing vote
            PollVote.objects.filter(poll=poll, user=request.user).delete()

            # Add new vote(s)
            selected_options = form.cleaned_data["options"]
            if isinstance(selected_options, PollOption):
                selected_options = [selected_options]

            for option in selected_options:
                PollVote.objects.create(poll=poll, option=option, user=request.user)

            messages.success(request, "Your vote has been recorded!")
        else:
            messages.error(request, "Please select at least one option.")

    return redirect("discussions:thread_detail", pk=poll.thread.pk)


@login_required
def manage_subscription(request, pk):
    """Manage thread subscription"""
    thread = get_object_or_404(DiscussionThread, pk=pk)

    subscription, created = DiscussionSubscription.objects.get_or_create(
        user=request.user, thread=thread, defaults={"subscription_type": "all"}
    )

    if request.method == "POST":
        form = DiscussionSubscriptionForm(request.POST, instance=subscription)
        if form.is_valid():
            form.save()
            messages.success(request, "Subscription updated successfully!")

    return redirect("discussions:thread_detail", pk=pk)


class TagListView(LoginRequiredMixin, ListView):
    """List all discussion tags"""

    model = DiscussionTag
    template_name = "discussions/tag_list.html"
    context_object_name = "tags"

    def get_queryset(self):
        return DiscussionTag.objects.annotate(
            thread_count=Count("tagged_threads")
        ).order_by("-usage_count", "name")


class TagDetailView(LoginRequiredMixin, DetailView):
    """View threads with a specific tag"""

    model = DiscussionTag
    template_name = "discussions/tag_detail.html"
    context_object_name = "tag"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tag = self.object

        threads = (
            DiscussionThread.objects.filter(thread_tags__tag=tag)
            .select_related("author", "forum")
            .order_by("-last_activity")
        )

        # Pagination
        paginator = Paginator(threads, 20)
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context["page_obj"] = page_obj
        context["threads"] = page_obj

        return context


@login_required
def search_discussions(request):
    """Search discussions across all forums"""
    form = DiscussionSearchForm(request.GET)
    threads = DiscussionThread.objects.none()

    if form.is_valid():
        query = form.cleaned_data.get("query")
        forum = form.cleaned_data.get("forum")
        author = form.cleaned_data.get("author")
        priority = form.cleaned_data.get("priority")
        status = form.cleaned_data.get("status")
        date_from = form.cleaned_data.get("date_from")
        date_to = form.cleaned_data.get("date_to")
        tags = form.cleaned_data.get("tags")

        # Start with base queryset
        threads = DiscussionThread.objects.select_related(
            "author", "forum"
        ).prefetch_related("tags")

        # Apply filters
        if query:
            threads = threads.filter(
                Q(title__icontains=query) | Q(content__icontains=query)
            )

        if forum:
            threads = threads.filter(forum=forum)

        if author:
            threads = threads.filter(author=author)

        if priority:
            threads = threads.filter(priority=priority)

        if status:
            threads = threads.filter(status=status)

        if date_from:
            threads = threads.filter(created_at__date__gte=date_from)

        if date_to:
            threads = threads.filter(created_at__date__lte=date_to)

        if tags:
            threads = threads.filter(thread_tags__tag__in=tags).distinct()

        threads = threads.order_by("-last_activity")

    # Pagination
    paginator = Paginator(threads, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "discussions/search_results.html",
        {
            "form": form,
            "page_obj": page_obj,
            "threads": page_obj,
            "query": request.GET.get("query", ""),
        },
    )


@login_required
def discussions_dashboard(request):
    """Discussions dashboard with statistics"""
    user = request.user

    # Get forums user can access
    if user.role in ["company_secretary", "it_administrator"]:
        forums = DiscussionForum.objects.all()
    else:
        forums = DiscussionForum.objects.filter(access_level="public", is_active=True)

    context = {
        "total_forums": forums.count(),
        "total_threads": DiscussionThread.objects.filter(forum__in=forums).count(),
        "total_posts": DiscussionPost.objects.filter(thread__forum__in=forums).count(),
        "my_threads": DiscussionThread.objects.filter(
            author=user, forum__in=forums
        ).order_by("-last_activity")[:5],
        "recent_threads": DiscussionThread.objects.filter(forum__in=forums).order_by(
            "-last_activity"
        )[:10],
        "popular_tags": DiscussionTag.objects.annotate(
            thread_count=Count("tagged_threads")
        ).order_by("-thread_count")[:10],
        "active_polls": DiscussionPoll.objects.filter(
            thread__forum__in=forums, ends_at__gt=timezone.now()
        ).order_by("-created_at")[:5],
    }

    return render(request, "discussions/discussions_dashboard.html", context)


# Forum Management (admin only)
class ForumCreateView(LoginRequiredMixin, CreateView):
    """Create a new discussion forum"""

    model = DiscussionForum
    form_class = DiscussionForumForm
    template_name = "discussions/forum_form.html"
    success_url = reverse_lazy("discussions:forum_list")

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ["company_secretary", "it_administrator"]:
            messages.error(request, "You don't have permission to create forums.")
            return redirect("discussions:forum_list")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(
            self.request, f"Forum '{form.instance.name}' created successfully!"
        )
        return super().form_valid(form)


# Tag Management
class TagCreateView(LoginRequiredMixin, CreateView):
    """Create a new discussion tag"""

    model = DiscussionTag
    form_class = DiscussionTagForm
    template_name = "discussions/tag_form.html"
    success_url = reverse_lazy("discussions:tag_list")

    def dispatch(self, request, *args, **kwargs):
        if request.user.role not in ["company_secretary", "it_administrator"]:
            messages.error(request, "You don't have permission to create tags.")
            return redirect("discussions:tag_list")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(
            self.request, f"Tag '{form.instance.name}' created successfully!"
        )
        return super().form_valid(form)
