from typing import Optional
import asyncio, logging # noqa: E401
from .models import WebhookTransaction  
from .exceptions import EventError
from .enums import EventFutureStatus


class FedapayEvent:

    _init = False
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(FedapayEvent, cls).__new__(cls)
        return cls._instance

    def __init__(self, logger: Optional[logging.Logger] = None):
        if self._init is False:
            self._logger = logger
            self.processed_events = set()
            self._processing_results_futures : dict[int, asyncio.Future] = {}
            self._event_data: dict[int, list[WebhookTransaction]] = {}
            self._asyncio_event_loop = asyncio.get_event_loop()
            self._init = True


    def create_future(self, id_transaction: int, timeout: Optional[float] = None) -> asyncio.Future:
        if id_transaction in self._processing_results_futures:
            self._logger.error(f"Future for id_transaction '{id_transaction}' already exists")
            raise EventError(f"Future for id_transaction '{id_transaction}' already exists")

        future = self._asyncio_event_loop.create_future()
        self._processing_results_futures[id_transaction] = future

        if timeout:
            asyncio.create_task(self._auto_cancel(id_transaction, timeout))
        self._logger.info(f"Future created for id_transaction '{id_transaction}' with timeout {timeout}")
        return future

    async def _auto_cancel(self, id_transaction: int, timeout: float):
        self._logger.info(f"Auto-cancel for id_transaction '{id_transaction}' started with timeout {timeout}")
        await asyncio.sleep(timeout)
        if id_transaction in self._processing_results_futures and not self._processing_results_futures[id_transaction].done():
            self._logger.info(f"Auto-cancel for id_transaction '{id_transaction}' triggered")
            future = self._processing_results_futures.pop(id_transaction, None)
            if future and not future.done():
                self._asyncio_event_loop.call_soon_threadsafe(future.set_result,EventFutureStatus.TIMEOUT)
        else:
            self._logger.info(f"Future for id_transaction '{id_transaction}' already resolved or cancelled before timeout")
        self._logger.info(f"Auto-cancel for id_transaction '{id_transaction}' completed")
            

    def resolve(self, id_transaction: int):
        self._logger.info(f"Resolving future for id_transaction '{id_transaction}'")
        future = self._processing_results_futures.pop(id_transaction, None)
        if future and not future.done():
            self._asyncio_event_loop.call_soon_threadsafe(future.set_result,EventFutureStatus.RESOLVED)
            self._logger.info(f"Future for id_transaction '{id_transaction}' resolved")
        else:
            self._logger.info(f"Future for id_transaction '{id_transaction}' already resolved or cancelled before")
            

    def cancel(self, id_transaction: int):
        self._logger.info(f"Cancelling future for id_transaction '{id_transaction}'")
        future = self._processing_results_futures.pop(id_transaction, None)
        if future and not future.done():
            self._asyncio_event_loop.call_soon_threadsafe(future.set_result,EventFutureStatus.CANCELLED)
            self._logger.info(f"Future for id_transaction '{id_transaction}' cancelled")
            return True
        else:
            self._logger.info(f"Future for id_transaction '{id_transaction}' already resolved or cancelled before")
        return False
    
    def cancel_all(self, reason: Optional[str] = "All waiting event cancelled by user"):
        self._logger.info(f"Cancelling all futures -- reason : {reason} ")
        for id in self._processing_results_futures.keys():
            future = self._processing_results_futures.pop(id, None)
            if future and not future.done():
                self._asyncio_event_loop.call_soon_threadsafe(future.set_result,EventFutureStatus.CANCELLED)
                self._logger.info(f"Future for id_transaction '{id}' cancelled")
            else:
                self._logger.info(f"Future for id_transaction '{id}' already resolved or cancelled before")

    def has_future(self, id_transaction: int) -> bool:
        return id_transaction in self._processing_results_futures

    def get_future(self, id_transaction: int) -> Optional[asyncio.Future]:
        return self._processing_results_futures.get(id_transaction, None)

    def set_event_data(self, data: WebhookTransaction):
        id_transaction = data.entity.id
        event_id = f"{data.entity.id}.{data.name}"
        if event_id in self.processed_events:
            self._logger.info(f"Event '{event_id}' already processed")
            return False
        self.processed_events.add(event_id)
        self._logger.info(f"Setting event data for id_transaction '{id_transaction}'")
        datalist = self._event_data.get(id_transaction, None)
        if datalist is None:
            self._event_data[id_transaction] = [data]
        else:
            datalist.append(data)
            self._event_data[id_transaction] = datalist
        self._logger.info(f"Event data for id_transaction '{id_transaction}' set")
        self.resolve(id_transaction)
        self._logger.info(f"Event data for id_transaction '{id_transaction}' resolved")
        return True
    
    def get_event_data(self, id_transaction: int) -> Optional[list[WebhookTransaction]]:
        self._logger.info(f"Getting event data for id_transaction '{id_transaction}'")
        return self._event_data.pop(id_transaction, None)