from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Channel, ChannelMembership, DirectThread, Message, Report, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Profil komunikatora", {"fields": ("role", "avatar", "bio", "is_blocked", "last_seen")}),)
    list_display = ("username", "email", "role", "is_blocked", "is_staff")
    list_filter = ("role", "is_blocked", "is_staff")


admin.site.register(Channel)
admin.site.register(ChannelMembership)
admin.site.register(DirectThread)
admin.site.register(Message)
admin.site.register(Report)
