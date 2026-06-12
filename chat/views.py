from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ChannelForm, MessageForm, ProfileForm, RegisterForm, ReportForm, RoleForm
from .models import Channel, ChannelMembership, DirectThread, Message, User


def require_moderator(user):
    if not user.can_moderate():
        raise PermissionDenied


def require_admin(user):
    if not user.can_administer():
        raise PermissionDenied


def touch_presence(user):
    User.objects.filter(pk=user.pk).update(last_seen=timezone.now())


def register(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            if User.objects.count() == 1:
                user.role = User.ADMIN
                user.is_staff = True
                user.save(update_fields=["role", "is_staff"])
            login(request, user)
            messages.success(request, "Konto zostalo utworzone.")
            return redirect("home")
    else:
        form = RegisterForm()
    return render(request, "registration/register.html", {"form": form})


@login_required
def home(request):
    touch_presence(request.user)
    first_channel = Channel.objects.first()
    if first_channel:
        return redirect(channel_url_name(first_channel), channel_id=first_channel.id)
    return render(request, "chat/home.html", context_data(request))


@login_required
def profile(request):
    touch_presence(request.user)
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil zostal zapisany.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "chat/profile.html", {**context_data(request), "form": form})


@login_required
def create_channel(request):
    require_admin(request.user)
    if request.method == "POST":
        form = ChannelForm(request.POST)
        if form.is_valid():
            channel = form.save(commit=False)
            channel.created_by = request.user
            channel.save()
            ChannelMembership.objects.get_or_create(channel=channel, user=request.user)
            messages.success(request, "Kanal zostal utworzony.")
            return redirect(channel_url_name(channel), channel_id=channel.id)
    else:
        form = ChannelForm()
    return render(request, "chat/channel_form.html", {**context_data(request), "form": form})


@login_required
def channel_detail(request, channel_id):
    touch_presence(request.user)
    channel = get_object_or_404(Channel, id=channel_id)
    if channel.channel_type == Channel.VOICE:
        return redirect("voice_channel", channel_id=channel.id)
    is_member = ChannelMembership.objects.filter(channel=channel, user=request.user).exists()
    messages_qs = channel.messages.select_related("author").order_by("-created_at")[:80]
    return render(
        request,
        "chat/channel.html",
        {
            **context_data(request, active_channel=channel),
            "channel": channel,
            "is_member": is_member,
            "messages_list": reversed(messages_qs),
            "message_form": MessageForm(),
        },
    )


@login_required
def voice_channel(request, channel_id):
    touch_presence(request.user)
    channel = get_object_or_404(Channel, id=channel_id, channel_type=Channel.VOICE)
    is_member = ChannelMembership.objects.filter(channel=channel, user=request.user).exists()
    return render(
        request,
        "chat/voice_channel.html",
        {
            **context_data(request, active_channel=channel),
            "channel": channel,
            "is_member": is_member,
        },
    )


@login_required
def join_channel(request, channel_id):
    channel = get_object_or_404(Channel, id=channel_id)
    ChannelMembership.objects.get_or_create(channel=channel, user=request.user)
    messages.success(request, f"Dolaczono do kanalu {channel.name}.")
    return redirect(channel_url_name(channel), channel_id=channel.id)


@login_required
@require_POST
def send_channel_message(request, channel_id):
    channel = get_object_or_404(Channel, id=channel_id, channel_type=Channel.TEXT)
    if request.user.is_blocked:
        return JsonResponse({"error": "Konto jest zablokowane."}, status=403)
    if not ChannelMembership.objects.filter(channel=channel, user=request.user).exists():
        return JsonResponse({"error": "Najpierw dolacz do kanalu."}, status=403)
    form = MessageForm(request.POST, request.FILES)
    if form.is_valid():
        message = form.save(commit=False)
        message.author = request.user
        message.channel = channel
        message.save()
        return JsonResponse(message_payload(message))
    return JsonResponse({"errors": form.errors}, status=400)


@login_required
def direct_message(request, user_id):
    touch_presence(request.user)
    other = get_object_or_404(User, id=user_id)
    if other == request.user:
        return redirect("profile")
    thread = (
        DirectThread.objects.filter(users=request.user)
        .filter(users=other)
        .distinct()
        .first()
    )
    if not thread:
        thread = DirectThread.objects.create()
        thread.users.add(request.user, other)
    messages_qs = thread.messages.select_related("author").order_by("-created_at")[:80]
    return render(
        request,
        "chat/direct.html",
        {
            **context_data(request),
            "thread": thread,
            "other": other,
            "messages_list": reversed(messages_qs),
            "message_form": MessageForm(),
        },
    )


@login_required
@require_POST
def send_direct_message(request, thread_id):
    thread = get_object_or_404(DirectThread, id=thread_id, users=request.user)
    if request.user.is_blocked:
        return JsonResponse({"error": "Konto jest zablokowane."}, status=403)
    form = MessageForm(request.POST, request.FILES)
    if form.is_valid():
        message = form.save(commit=False)
        message.author = request.user
        message.direct_thread = thread
        message.save()
        return JsonResponse(message_payload(message))
    return JsonResponse({"errors": form.errors}, status=400)


@login_required
@require_POST
def delete_message(request, message_id):
    message = get_object_or_404(Message, id=message_id)
    if not (request.user == message.author or request.user.can_moderate()):
        raise PermissionDenied
    message.is_deleted = True
    message.content = ""
    message.image.delete(save=False)
    message.audio.delete(save=False)
    message.save(update_fields=["is_deleted", "content", "image", "audio"])
    return redirect(request.META.get("HTTP_REFERER", "home"))


@login_required
@require_POST
def react_message(request, message_id, emoji):
    message = get_object_or_404(Message, id=message_id)
    allowed = {"like": "👍", "heart": "❤️", "laugh": "😄"}
    symbol = allowed.get(emoji)
    if not symbol:
        return JsonResponse({"error": "Nieznana reakcja."}, status=400)
    reactions = message.reactions
    users = set(reactions.get(symbol, []))
    username = request.user.username
    if username in users:
        users.remove(username)
    else:
        users.add(username)
    reactions[symbol] = sorted(users)
    message.reactions = reactions
    message.save(update_fields=["reactions"])
    return redirect(request.META.get("HTTP_REFERER", "home"))


@login_required
def user_directory(request):
    touch_presence(request.user)
    query = request.GET.get("q", "").strip()
    users = User.objects.exclude(pk=request.user.pk).order_by("username")
    channels = Channel.objects.order_by("name")
    if query:
        users = users.filter(Q(username__icontains=query) | Q(email__icontains=query))
        channels = channels.filter(Q(name__icontains=query) | Q(description__icontains=query))
    return render(request, "chat/users.html", {**context_data(request), "users_list": users, "channels_list": channels, "query": query})


@login_required
def edit_user_role(request, user_id):
    require_admin(request.user)
    target = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        form = RoleForm(request.POST, instance=target)
        if form.is_valid():
            form.save()
            messages.success(request, "Uprawnienia uzytkownika zostaly zapisane.")
            return redirect("user_directory")
    else:
        form = RoleForm(instance=target)
    return render(request, "chat/role_form.html", {**context_data(request), "form": form, "target": target})


@login_required
def report_user(request, user_id):
    reported = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.reporter = request.user
            report.reported_user = reported
            report.save()
            messages.success(request, "Zgloszenie zostalo przekazane moderatorom.")
            return redirect("user_directory")
    else:
        form = ReportForm()
    return render(request, "chat/report_form.html", {**context_data(request), "form": form, "reported": reported})


def context_data(request, active_channel=None):
    channels = Channel.objects.all()
    direct_users = User.objects.exclude(pk=request.user.pk).order_by("username")[:12] if request.user.is_authenticated else []
    return {"channels": channels, "direct_users": direct_users, "active_channel": active_channel}


def channel_url_name(channel):
    return "voice_channel" if channel.channel_type == Channel.VOICE else "channel"


def message_payload(message):
    return {
        "id": message.id,
        "author": message.author.username,
        "content": message.visible_content(),
        "image": message.image.url if message.image else "",
        "audio": message.audio.url if message.audio else "",
        "created_at": message.created_at.strftime("%H:%M"),
    }


def page_not_found(request, exception):
    return render(request, "404.html", status=404)
