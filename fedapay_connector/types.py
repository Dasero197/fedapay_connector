from fedapay_connector.schemas import PaymentHistory, WebhookHistory
from typing import Callable, Awaitable

OperationCallback = Callable[[PaymentHistory], Awaitable[None]]
WebhookCallback = Callable[[WebhookHistory], Awaitable[None]]
