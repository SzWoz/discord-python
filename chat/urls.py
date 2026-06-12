from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("profile/", views.profile, name="profile"),
    path("channels/create/", views.create_channel, name="create_channel"),
    path("channels/<int:channel_id>/", views.channel_detail, name="channel"),
    path("channels/<int:channel_id>/voice/", views.voice_channel, name="voice_channel"),
    path("channels/<int:channel_id>/join/", views.join_channel, name="join_channel"),
    path("channels/<int:channel_id>/send/", views.send_channel_message, name="send_channel_message"),
    path("dm/<int:user_id>/", views.direct_message, name="direct_message"),
    path("dm/thread/<int:thread_id>/send/", views.send_direct_message, name="send_direct_message"),
    path("messages/<int:message_id>/delete/", views.delete_message, name="delete_message"),
    path("messages/<int:message_id>/react/<str:emoji>/", views.react_message, name="react_message"),
    path("users/", views.user_directory, name="user_directory"),
    path("users/<int:user_id>/role/", views.edit_user_role, name="edit_user_role"),
    path("users/<int:user_id>/report/", views.report_user, name="report_user"),
]
