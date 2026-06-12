from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/channel/(?P<channel_id>\d+)/$", consumers.ChannelConsumer.as_asgi()),
    re_path(r"ws/dm/(?P<thread_id>\d+)/$", consumers.DirectConsumer.as_asgi()),
    re_path(r"ws/voice/(?P<channel_id>\d+)/$", consumers.VoiceConsumer.as_asgi()),
]
