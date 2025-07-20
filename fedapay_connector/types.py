from .enums import EventFutureStatus
from .models import PaymentHistory, WebhookHistory, ListeningProcessData, WebhookTransaction
from typing import Callable, Awaitable

PaymentCallback = Callable[[PaymentHistory], Awaitable[None]]
WebhookCallback = Callable[[WebhookHistory], Awaitable[None]]
RunBeforeTimemoutCallback = Callable[[int], Awaitable[bool]]
RunAtPersistedProcessReloadCallback = Callable[[ListeningProcessData], Awaitable[None]]
OnPersistedProcessReloadFinishedCallback = Callable[[EventFutureStatus,list[WebhookTransaction] | None], Awaitable[None]]


