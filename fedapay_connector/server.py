from fastapi import FastAPI, HTTPException, Request, status
from  typing import Optional
import os, logging, uvicorn, threading  # noqa: E401
from .types import WebhookCallback
from .utils import verify_signature

class WebhookServer:
    def __init__(self,logger: logging.Logger, endpoint: str, port: Optional[int]= 3000, fedapay_auth_key: Optional[str]= os.getenv("FEDAPAY_AUTH_KEY")):
        self.logger = logger
        self.fedapay_auth_key = fedapay_auth_key
        if self.fedapay_auth_key:
            self.server_thread = None        
            self.endpoint = endpoint
            self.port = port
            self.app = FastAPI()
            self.logger.info(f"Webhook server initialized on {self.endpoint}:{self.port}")
        else:
            self.logger.error("Fedapay authentication key is not set. Webhook server will not be initialized.")
            raise ValueError("Fedapay authentication key is not set. Webhook server will not be initialized.")

    
    def _setup_routes(self, function_callback: Optional[WebhookCallback] = None):
        from .connector import FedapayConnector
        fd = FedapayConnector()

        @self.app.post(f"/{self.endpoint}", status_code=status.HTTP_200_OK)
        async def receive_webhooks(request: Request):
            header = request.headers
            agregateur = str(header.get("agregateur"))
            payload = await request.body()

            if not agregateur == "Fedapay":
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"Aggrégateur non reconnu : {agregateur}")
            
            verify_signature(
                payload,
                header.get("x-fedapay-signature"),
                self.fedapay_auth_key
            )
            
            event = await request.json()
            fd.fedapay_save_webhook_data(
                event)
            
            return {"ok"}
        
    def _start_webhook_server(self,  function_callback: Optional[WebhookCallback] = None):

        self._setup_routes(function_callback)
        try:
            uvicorn.run(self.app, host= "localhost", port= self.port, log_level="info")
            self.logger.info(f"Webhook server started at {self.endpoint}:{self.port}")
        except OSError as e:
            if e.errno == 98:
                self.logger.error(f"Port {self.port} is already in use. Please choose a different port.")
                raise e
            else:
                self.logger.error(f"Error starting webhook server: {e}")
                raise e
        except Exception as e:
            self.logger.error(f"Error starting webhook server: {e}")
            raise e
    
    def start_webhook_listenning(self, function_callback: Optional[WebhookCallback] = None):
        """
        Start the webhook server to listen for incoming requests.
        """
        try:
            self.server_thread = threading.Thread(target=self._start_webhook_server, args=[function_callback], daemon= True)
            self.server_thread.start()
            self.logger.info("Webhook server thread started.")
        except Exception as e:
            self.logger.error(f"Error starting webhook server: {e}")
            raise e