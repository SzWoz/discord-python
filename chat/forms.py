from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Channel, Message, Report, User


class RegisterForm(UserCreationForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["avatar", "bio"]
        widgets = {"bio": forms.Textarea(attrs={"rows": 3})}


class RoleForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["role", "is_blocked"]


class ChannelForm(forms.ModelForm):
    class Meta:
        model = Channel
        fields = ["name", "description", "channel_type"]


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["content", "image", "audio"]
        widgets = {"content": forms.TextInput(attrs={"placeholder": "Napisz wiadomosc..."})}


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["reason"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 4})}
