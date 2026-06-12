import json

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Channel, ChannelMembership, DirectThread, Message
from .views import message_payload


class BaseChatConsumer(AsyncWebsocketConsumer):
    async def receive(self, text_data):
        data = json.loads(text_data)
        content = data.get("content", "").strip()
        if not content or self.scope["user"].is_blocked:
            return
        message = await self.create_message(content)
        payload = await sync_to_async(message_payload)(message)
        await self.channel_layer.group_send(self.group_name, {"type": "chat.message", "message": payload})

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event["message"]))


class ChannelConsumer(BaseChatConsumer):
    async def connect(self):
        self.channel_id = self.scope["url_route"]["kwargs"]["channel_id"]
        self.group_name = f"channel_{self.channel_id}"
        user = self.scope["user"]
        allowed = await self.can_access(user)
        if not user.is_authenticated or not allowed:
            await self.close()
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    @sync_to_async
    def can_access(self, user):
        return ChannelMembership.objects.filter(channel_id=self.channel_id, user=user).exists()

    @sync_to_async
    def create_message(self, content):
        return Message.objects.create(channel_id=self.channel_id, author=self.scope["user"], content=content)


class DirectConsumer(BaseChatConsumer):
    async def connect(self):
        self.thread_id = self.scope["url_route"]["kwargs"]["thread_id"]
        self.group_name = f"dm_{self.thread_id}"
        user = self.scope["user"]
        allowed = await self.can_access(user)
        if not user.is_authenticated or not allowed:
            await self.close()
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    @sync_to_async
    def can_access(self, user):
        return DirectThread.objects.filter(id=self.thread_id, users=user).exists()

    @sync_to_async
    def create_message(self, content):
        return Message.objects.create(direct_thread_id=self.thread_id, author=self.scope["user"], content=content)


class VoiceConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.channel_id = self.scope["url_route"]["kwargs"]["channel_id"]
        self.group_name = f"voice_{self.channel_id}"
        self.username = self.scope["user"].username
        user = self.scope["user"]
        allowed = await self.can_access(user)
        if not user.is_authenticated or not allowed:
            await self.close()
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "voice.signal", "payload": {"type": "user-joined", "from": self.username}},
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "voice.signal", "payload": {"type": "user-left", "from": self.username}},
        )
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        payload = json.loads(text_data)
        payload["from"] = self.username
        await self.channel_layer.group_send(self.group_name, {"type": "voice.signal", "payload": payload})

    async def voice_signal(self, event):
        if event["payload"].get("from") == self.username:
            return
        await self.send(text_data=json.dumps(event["payload"]))

    @sync_to_async
    def can_access(self, user):
        return ChannelMembership.objects.filter(channel_id=self.channel_id, user=user, channel__channel_type=Channel.VOICE).exists()
