import os
from typing import Optional
import asyncio
import logging

from .db_models import StoredListeningProcess
from .types import (
    RunAtPersistedProcessReloadCallback,
    RunBeforeTimemoutCallback,
)

from .event_storage import ProcessPersistance  # noqa: E401
from .models import WebhookTransaction, ListeningProcessData
from .exceptions import EventError
from .enums import EventFutureStatus, ExceptionOnProcessReloadBehavior


class FedapayEvent:
    _init = False
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(FedapayEvent, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        logger: logging.Logger,
        max_reload_attempts: int,
        on_listening_reload_exception: ExceptionOnProcessReloadBehavior,
        final_event_names: list[str],
        sleeping_before_retry_delay: Optional[float] = 5,
        db_url: Optional[str] = os.getenv(
            "FEDAPAY_DB_URL", "sqlite:///fedapay_connector_persisted_data/processes.db"
        ),
    ):
        if self._init is False:
            self._logger = logger
            self.processed_events = set()
            self._processing_results_futures_lock = asyncio.Lock()
            self._processing_results_futures: dict[int, asyncio.Future] = {}
            self._event_data: dict[int, list[WebhookTransaction]] = {}
            self._asyncio_event_loop = asyncio.get_event_loop()
            self._event_persit_storage = ProcessPersistance(
                logger=logger, db_url=db_url
            )
            self._run_before_timeout_callback: Optional[RunBeforeTimemoutCallback] = (
                None
            )
            self._run_at_persisted_process_reload_callback: Optional[
                RunAtPersistedProcessReloadCallback
            ] = None
            self.max_reload_attempts = max_reload_attempts
            self.on_listening_reload_exception = on_listening_reload_exception
            self.retry_attempts = {}
            self.sleeping_before_retry_delay = sleeping_before_retry_delay
            self.final_event_names = final_event_names
            self._init = True

    async def _auto_cancel(self, id_transaction: int, timeout: float):
        self._logger.info(
            f"Auto-cancel for id_transaction '{id_transaction}' started with timeout {timeout}"
        )
        await asyncio.sleep(timeout)
        if (
            id_transaction in self._processing_results_futures
            and not self._processing_results_futures[id_transaction].done()
        ):
            self._logger.info(
                f"Auto-cancel for id_transaction '{id_transaction}' triggered"
            )

            if self._run_before_timeout_callback:
                try:
                    should_cancel = await self._run_before_timeout_callback(
                        id_transaction
                    )
                    if not should_cancel:
                        self._logger.info(
                            f"Auto-cancel for id_transaction '{id_transaction}' skipped by callback"
                        )
                        return await self.resolve(id_transaction=id_transaction)
                except Exception as e:
                    self._logger.error(
                        f"Error in run_before_timeout_callback for id_transaction '{id_transaction}': {e} -- timeouting by default"
                    )
                    pass

            async with self._processing_results_futures_lock:
                future = self._processing_results_futures.pop(id_transaction, None)
            if future and not future.done():
                self._asyncio_event_loop.call_soon_threadsafe(
                    future.set_result, EventFutureStatus.TIMEOUT
                )
            self._event_persit_storage.delete_process(transaction_id=id_transaction)
        else:
            self._logger.info(
                f"Future for id_transaction '{id_transaction}' already resolved or cancelled before timeout"
            )
        self._logger.info(
            f"Auto-cancel for id_transaction '{id_transaction}' completed"
        )

    def _persisted_process_reload_callback_exception(self, task: asyncio.Task):
        try:
            task.result()

        except Exception as e:
            self._logger.debug(
                f"Erreur dans le persisted_process_reload_callback : {e}",
                stack_info=True,
            )

    async def _load_persisted_process(self, process: StoredListeningProcess):
        if self._run_at_persisted_process_reload_callback:
            try:
                task = asyncio.create_task(
                    self._run_at_persisted_process_reload_callback(
                        ListeningProcessData.model_validate_json(
                            process.StoredListeningProcess_process_data
                        )
                    )
                )
                task.add_done_callback(
                    self._persisted_process_reload_callback_exception
                )
                # si la tache est créer le rôle de cette persistance est atteint donc la perisitance est supprimée
                # si entre ce moment et le moment ou la tache est executée le backend est redemarrer ou arreté
                # avant l'exec de reload_future, le process d'ecoute est definitivement perdu pace que la creation du future s'ocuppe
                # elle meme de la persistance si necessaire et si la tache lancé ici peut ne pas aboutir a
                # un reload_future en fonction de l'exec du callback

                self._event_persit_storage.delete_process(
                    transaction_id=process.StoredListeningProcess_transaction_id
                )
                self._logger.info(
                    f"run_at_persisted_process_reload_callback for process {process.StoredListeningProcess_transaction_id} completed successfully"
                )
            except Exception as e:
                self._logger.error(
                    f"Error in run_at_persisted_process_reload_callback for process {process.StoredListeningProcess_transaction_id}: {e} -- loading failled"
                )
                if (
                    self.on_listening_reload_exception
                    == ExceptionOnProcessReloadBehavior.DROP_AND_REMOVE_PERSISTANCE
                ):
                    self._logger.error(
                        f"Removing persisted process {process.StoredListeningProcess_transaction_id} due to reload exception"
                    )
                    self._event_persit_storage.delete_process(
                        transaction_id=process.StoredListeningProcess_transaction_id
                    )
                elif (
                    self.on_listening_reload_exception
                    == ExceptionOnProcessReloadBehavior.DROP_AND_KEEP_PERSISTED
                ):
                    self._logger.error(
                        f"Dropping persisted process {process.StoredListeningProcess_transaction_id} due to reload exception but keeping it in persistence"
                    )

                elif (
                    self.on_listening_reload_exception
                    == ExceptionOnProcessReloadBehavior.KEEP_AND_RETRY
                ):
                    self._logger.error(
                        f"Keeping persisted process {process.StoredListeningProcess_transaction_id} and retrying later"
                    )
                    retry_count = self.retry_attempts.get(
                        process.StoredListeningProcess_transaction_id, None
                    )
                    if retry_count is None:
                        retry_count = 0
                    if retry_count < self.max_reload_attempts:
                        self.retry_attempts[
                            process.StoredListeningProcess_transaction_id
                        ] = retry_count + 1
                        await asyncio.sleep(self.sleeping_before_retry_delay)
                        asyncio.create_task(self._load_persisted_process(process))

                    self._logger.error(
                        f"maximum retry attempts reached for process {process.StoredListeningProcess_transaction_id}"
                    )

                else:
                    self._logger.error(
                        f"Unknown behavior for process {process.StoredListeningProcess_transaction_id} due to reload exception"
                    )
                    raise e

    def set_run_before_timeout_callback(self, callback: RunBeforeTimemoutCallback):
        self._run_before_timeout_callback = callback

    def set_run_at_persisted_process_reload_callback(
        self, callback: RunAtPersistedProcessReloadCallback
    ):
        self._run_at_persisted_process_reload_callback = callback

    async def resolve_if_final_event_already_received(self, id_transaction):
        """
        Vérifie si un event final n'a pas deja été reçu avant la mise en place de l'ecoute

        Dans certains cas fedapay retourne la webhook immediatement et pour eviter d'attendre un future qui est deja résolu on peut verifier avec cette fonction

        """
        events = self._event_data.get(id_transaction, None)
        if events is None:
            return False
        for event in events:
            if event.name in self.final_event_names:
                self._logger.info(
                    f"Final event '{event.name}' already received for id_transaction '{id_transaction}'"
                )
                await self.resolve(id_transaction)
                return True
        return False

    async def create_future(
        self, id_transaction: int, timeout: Optional[float] = None
    ) -> asyncio.Future:
        if id_transaction in self._processing_results_futures:
            self._logger.error(
                f"Future for id_transaction '{id_transaction}' already exists"
            )
            raise EventError(
                f"Future for id_transaction '{id_transaction}' already exists"
            )

        future = self._asyncio_event_loop.create_future()
        async with self._processing_results_futures_lock:
            self._processing_results_futures[id_transaction] = future

        if timeout:
            asyncio.create_task(self._auto_cancel(id_transaction, timeout))
        self._logger.info(
            f"Future created for id_transaction '{id_transaction}' with timeout {timeout}"
        )
        self._event_persit_storage.save_process(
            transaction_id=id_transaction,
            process_data=ListeningProcessData(id_transaction=id_transaction),
        )

        return future

    async def reload_future(
        self, process_data: ListeningProcessData, timeout: Optional[float] = None
    ) -> asyncio.Future:
        if process_data.id_transaction in self._processing_results_futures:
            self._logger.error(
                f"Future for id_transaction '{process_data.id_transaction}' already exists"
            )
            raise EventError(
                f"Future for id_transaction '{process_data.id_transaction}' already exists"
            )

        future = self._asyncio_event_loop.create_future()
        async with self._processing_results_futures_lock:
            self._processing_results_futures[process_data.id_transaction] = future

        if timeout:
            asyncio.create_task(self._auto_cancel(process_data.id_transaction, timeout))
        self._logger.info(
            f"Future created for id_transaction '{process_data.id_transaction}' with timeout {timeout}"
        )
        self._event_persit_storage.save_process(
            transaction_id=process_data.id_transaction, process_data=process_data
        )

        return future

    async def resolve(self, id_transaction: int):
        self._logger.info(f"Resolving future for id_transaction '{id_transaction}'")
        async with self._processing_results_futures_lock:
            future = self._processing_results_futures.pop(id_transaction, None)
        if future and not future.done():
            self._asyncio_event_loop.call_soon_threadsafe(
                future.set_result, EventFutureStatus.RESOLVED
            )
            self._event_persit_storage.delete_process(transaction_id=id_transaction)
            self._logger.info(f"Future for id_transaction '{id_transaction}' resolved")
        else:
            self._logger.info(
                f"Future for id_transaction '{id_transaction}' already resolved or cancelled before"
            )

    async def cancel(self, id_transaction: int, lock_acquire: bool = True):
        self._logger.info(f"Cancelling future for id_transaction '{id_transaction}'")
        if lock_acquire:
            async with self._processing_results_futures_lock:
                future = self._processing_results_futures.pop(id_transaction, None)
        else:
            future = self._processing_results_futures.pop(id_transaction, None)

        if future and not future.done():
            self._asyncio_event_loop.call_soon_threadsafe(
                future.set_result, EventFutureStatus.CANCELLED
            )
            self._event_persit_storage.delete_process(transaction_id=id_transaction)
            self._logger.info(f"Future for id_transaction '{id_transaction}' cancelled")
            return True
        else:
            self._logger.info(
                f"Future for id_transaction '{id_transaction}' already resolved or cancelled before"
            )
        return False

    async def cancel_all(
        self, reason: Optional[str] = "All waiting event cancelled by user"
    ):
        self._logger.info(f"Cancelling all futures -- reason : {reason} ")
        async with self._processing_results_futures_lock:
            keys = list(self._processing_results_futures.keys())
            for id in keys:
                try:
                    await self.cancel(id, False)
                except Exception as e:
                    self._logger.error(
                        f"Error cancelling future for id_transaction '{id}': {e} -- dropping future cancelling"
                    )

    def has_future(self, id_transaction: int) -> bool:
        return id_transaction in self._processing_results_futures

    def get_future(self, id_transaction: int) -> Optional[asyncio.Future]:
        return self._processing_results_futures.get(id_transaction, None)

    async def set_event_data(self, data: WebhookTransaction):
        id_transaction = data.entity.id
        event_id = f"{data.entity.id}.{data.name}"
        if event_id in self.processed_events:
            self._logger.info(f"Event '{event_id}' already processed")
            return False
        self.processed_events.add(event_id)
        self._logger.info(f"Setting event data for id_transaction '{id_transaction}'")
        datalist = self._event_data.get(id_transaction, None)
        if datalist is None:
            datalist = [data]
        else:
            datalist.append(data)

        self._event_data[id_transaction] = datalist
        self._event_persit_storage.update_process(
            transaction_id=id_transaction,
            process_data=ListeningProcessData(
                id_transaction=id_transaction, received_webhooks=datalist
            ),
        )

        # pas besoin de verifier le type d'event reçu vu que la selection est faite en amont pour filtrer
        # les event et que tous les event sont exclusif l'un pour l'autre

        self._logger.info(f"Event data for id_transaction '{id_transaction}' set")

        await self.resolve(id_transaction)
        self._logger.info(f"Event data for id_transaction '{id_transaction}' resolved")
        return True

    def pop_event_data(self, id_transaction: int) -> Optional[list[WebhookTransaction]]:
        self._logger.info(f"Getting event data for id_transaction '{id_transaction}'")
        self._event_persit_storage.delete_process(transaction_id=id_transaction)
        return self._event_data.pop(id_transaction, None)

    async def load_persisted_processes(self):
        self._logger.info("Loading persisted processes")
        print(
            "[FEDAPAY CONNECTOR WARNING] Loading persisted processes ongoing please don't stop or restart process until finished or you may loose listening for fedapay webhook event"
        )
        processes = self._event_persit_storage.load_processes()
        for process in processes:
            await self._load_persisted_process(process)
        self._logger.info("Loading persisted processes finished")
        print("[FEDAPAY CONNECTOR INFO] Loading persisted processes finished")
