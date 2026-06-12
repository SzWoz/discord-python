from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    ADMIN = "admin"
    MODERATOR = "moderator"
    MEMBER = "member"

    ROLE_CHOICES = [
        (ADMIN, "Administrator"),
        (MODERATOR, "Moderator"),
        (MEMBER, "Uzytkownik"),
    ]

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=MEMBER)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio = models.TextField(blank=True)
    is_blocked = models.BooleanField(default=False)
    last_seen = models.DateTimeField(default=timezone.now)

    def can_administer(self):
        return self.role == self.ADMIN or self.is_superuser

    def can_moderate(self):
        return self.can_administer() or self.role == self.MODERATOR

    def is_online(self):
        return self.last_seen >= timezone.now() - timezone.timedelta(minutes=5)


class Channel(models.Model):
    TEXT = "text"
    VOICE = "voice"

    TYPE_CHOICES = [
        (TEXT, "Tekstowy"),
        (VOICE, "Glosowy"),
    ]

    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=180, blank=True)
    channel_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TEXT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, through="ChannelMembership", related_name="channels")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ChannelMembership(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("channel", "user")


class DirectThread(models.Model):
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="direct_threads")
    created_at = models.DateTimeField(auto_now_add=True)

    def other_user(self, user):
        return self.users.exclude(pk=user.pk).first()


class Message(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, null=True, blank=True, related_name="messages")
    direct_thread = models.ForeignKey(DirectThread, on_delete=models.CASCADE, null=True, blank=True, related_name="messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="messages")
    content = models.TextField(blank=True)
    image = models.ImageField(upload_to="message_images/", blank=True, null=True)
    audio = models.FileField(upload_to="message_audio/", blank=True, null=True)
    reactions = models.JSONField(default=dict, blank=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def visible_content(self):
        return "[wiadomosc usunieta]" if self.is_deleted else self.content


class Report(models.Model):
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_made")
    reported_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_received")
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
