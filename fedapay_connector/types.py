from .models import PaymentHistory, WebhookHistory
from typing import Callable, Awaitable

PaymentCallback = Callable[[PaymentHistory], Awaitable[None]]
WebhookCallback = Callable[[WebhookHistory], Awaitable[None]]
