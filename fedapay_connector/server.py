import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from typing import Optional
import os, logging, uvicorn, threading  # noqa: E401
from .utils import verify_signature


class WebhookServer:
    def __init__(
        self,
        logger: logging.Logger,
        endpoint: str,
        port: Optional[int] = 3000,
        fedapay_auth_key: Optional[str] = os.getenv("FEDAPAY_AUTH_KEY"),
        shutdown_timeout: int = 10,
        thread_join_timeout: int = 1,
    ):
        self.logger = logger
        self.fedapay_auth_key = fedapay_auth_key
        if self.fedapay_auth_key:
            self.server_thread = None
            self.endpoint = endpoint
            self.port = port
            self.app = FastAPI(lifespan=self._fastapi_lifespan)
            self.logger.info(
                f"Webhook server initialized on {self.endpoint}:{self.port}"
            )
            self.shutdown_event = threading.Event()
            self.shutdown_complete_event = threading.Event()
            self.shutdown_timeout = shutdown_timeout
            self.thread_join_timeout = thread_join_timeout
            self.is_running = False
        else:
            self.logger.error(
                "Fedapay authentication key is not set. Webhook server will not be initialized."
            )
            raise ValueError(
                "Fedapay authentication key is not set. Webhook server will not be initialized."
            )

    @asynccontextmanager
    async def _fastapi_lifespan(self, app: FastAPI):
        """
        Lifespan event handler for FastAPI to manage startup and shutdown.
        """

        self.logger.info("Fastapi is starting...")
        # mettre tout ce qu'on veut faire executer par fastapi dans son thread au demarrage ici

        asyncio.create_task(
            self._watch_shutdown_signal()
        )  # pour ne pas interferer avec
        # la boucle d'event de fastapi en creant une manuellement pour le thread serveur on passe la fonction a
        # fastapi pour qu'il l'execute lui meme dans la boucle asyncio de fastapi ainsi on est sur que le code est au bon endroit

        yield
        self.logger.info("Fastapi is shutting down.")
        # mettre tout ce qu'on veut faire executer par fastapi dans son thread à l'arret ici

    async def _watch_shutdown_signal(self):
        """
        Watch for shutdown signal and gracefully stop the webhook server."""
        self.logger.info("Watching for shutdown signal...")
        while not self.shutdown_event.is_set():
            await asyncio.sleep(0.1)
        await self._shutdown_webhook_server()

    def _setup_routes(self):
        from .connector import FedapayConnector

        @self.app.post(f"/{self.endpoint}", status_code=status.HTTP_200_OK)
        async def receive_webhooks(request: Request):
            header = request.headers
            agregateur = str(header.get("agregateur"))
            payload = await request.body()

            if not agregateur == "Fedapay":
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, f"Aggrégateur non reconnu : {agregateur}"
                )

            verify_signature(
                payload, header.get("x-fedapay-signature"), self.fedapay_auth_key
            )

            event = await request.json()
            await FedapayConnector().fedapay_save_webhook_data(event)

            return {"ok"}

    def _start_webhook_server(self):
        self._setup_routes()
        config = uvicorn.Config(
            app=self.app, host="localhost", port=self.port, log_level="info"
        )
        self.server = uvicorn.Server(config)

        try:
            self.logger.info(
                f"Webhook server is starting at {self.endpoint}:{self.port}"
            )
            self.server.run()  # run etant bloquant si on passe a la ligne suivante dans lexec c'est que le serveur ne tourne plus
            self.logger.info("Webhook server stopped successfully.")
        except OSError as e:
            if e.errno == 98:
                self.logger.error(
                    f"Port {self.port} is already in use. Please choose a different port."
                )
                raise e
            else:
                self.logger.error(f"Error starting webhook server: {e}")
                raise e
        except Exception as e:
            self.logger.error(f"Error starting webhook server: {e}")
            raise e

    async def _shutdown_webhook_server(self):
        """Arrête proprement le serveur de l'interieur"""
        if self.server:
            self.logger.info("Shutting down webhook server...")
            await self.server.shutdown()
            self.shutdown_complete_event.set()

    def start_webhook_listenning(self):
        """
        Start the webhook server to listen for incoming requests.
        """
        if self.is_running:
            self.logger.warning("Webhook server is already running")
            return

        try:
            self.server_thread = threading.Thread(
                target=self._start_webhook_server, daemon=True
            )
            self.server_thread.start()
            self.logger.info("Webhook server thread started.")
            self.is_running = True

        except Exception as e:
            self.logger.error(f"Error starting webhook server: {e}")
            raise e

    def stop_webhook_listenning(self):
        """
        Stop the webhook server.
        """

        if not self.is_running:
            self.logger.warning("Webhook server is not running")
            return
        try:
            if self.server_thread and self.server_thread.is_alive():
                self.shutdown_event.set()
                self.shutdown_complete_event.wait(self.shutdown_timeout)
                self.server_thread.join(timeout=self.thread_join_timeout)
                if self.server_thread.is_alive():
                    self.logger.warning(
                        "Le thread du serveur webhook n'a pas pu être arrêté proprement"
                    )
                else:
                    self.logger.info("Webhook server thread stopped.")
            else:
                self.logger.warning(
                    "Webhook server thread is not running or already stopped."
                )
        except Exception as e:
            self.logger.error(f"Error during server shutdown: {e}")
        finally:
            self.is_running = False
            self.shutdown_event.clear()
            self.shutdown_complete_event.clear()
