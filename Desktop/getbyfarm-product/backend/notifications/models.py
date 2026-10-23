import uuid
from abc import ABC, abstractmethod
from django.db import models
from accounts.models import User


CHANNEL_CHOICES = [("email", "Email"), ("sms", "SMS"), ("in_app", "In-App"), ("whatsapp", "WhatsApp")]


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    title = models.CharField(max_length=150)
    body = models.TextField()
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class NotificationChannel(ABC):
    @abstractmethod
    def send(self, user: User, title: str, body: str) -> bool:
        ...


class InAppChannel(NotificationChannel):
    """[Implemented] — the only channel that's fully real in MVP; just writes a row."""

    def send(self, user, title, body) -> bool:
        Notification.objects.create(user=user, channel="in_app", title=title, body=body)
        return True


class MockEmailChannel(NotificationChannel):
    """[Mocked] — logs instead of sending. Wire to SES/SendGrid/etc. via env-configured credentials."""

    def send(self, user, title, body) -> bool:
        Notification.objects.create(user=user, channel="email", title=title, body=body)
        print(f"[MOCK EMAIL] to={user.email} subject={title!r}")
        return True


class MockSmsChannel(NotificationChannel):
    """[Mocked] — logs instead of sending. Wire to Africa's Talking / Twilio via env credentials."""

    def send(self, user, title, body) -> bool:
        Notification.objects.create(user=user, channel="sms", title=title, body=body)
        print(f"[MOCK SMS] to={user.phone} body={body!r}")
        return True


class WhatsAppChannel(NotificationChannel):
    """
    [Future] — architecture placeholder per spec section 32. Not implemented: requires
    a WhatsApp Business API / BSP account and message-template approval. Raises so it's
    never silently mistaken for a working channel.
    """

    def send(self, user, title, body) -> bool:
        raise NotImplementedError(
            "WhatsApp notifications are architected for but not implemented. "
            "Requires a WhatsApp Business Platform account and approved message templates."
        )


CHANNELS: dict[str, NotificationChannel] = {
    "in_app": InAppChannel(),
    "email": MockEmailChannel(),
    "sms": MockSmsChannel(),
    "whatsapp": WhatsAppChannel(),
}


def notify(user: User, title: str, body: str, channels: list[str] = ("in_app",)):
    """Fan out a notification across one or more channels, skipping ones that aren't implemented."""
    results = {}
    for channel_name in channels:
        channel = CHANNELS.get(channel_name)
        if not channel:
            continue
        try:
            results[channel_name] = channel.send(user, title, body)
        except NotImplementedError as exc:
            results[channel_name] = f"skipped: {exc}"
    return results
