"""
FedaPay Connector

Copyright (C) 2025 ASSOGBA Dayane

Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
conformément aux termes de la GNU Affero General Public License publiée par la
Free Software Foundation, soit la version 3 de la licence, soit (à votre choix)
toute version ultérieure.

Ce programme est distribué dans l'espoir qu'il sera utile,
mais SANS AUCUNE GARANTIE ; sans même la garantie implicite de
COMMERCIALISATION ou D'ADÉQUATION À UN OBJECTIF PARTICULIER.
Consultez la GNU Affero General Public License pour plus de détails.

Vous devriez avoir reçu une copie de la GNU Affero General Public License
avec ce programme. Si ce n'est pas le cas, consultez <https://www.gnu.org/licenses/>.
"""

from .enums import EventFutureStatus, TypesPaiement
from .event import FedapayEvent
from .models import FedapayStatus, PaiementSetup, UserData, PaymentHistory, WebhookHistory, WebhookTransaction, InitTransaction, FedapayPay, GetToken
from .utils import initialize_logger, get_currency
from .types import WebhookCallback, PaymentCallback
from .server import WebhookServer
from typing import Optional
import os, asyncio, aiohttp, inspect  # noqa: E401

class FedapayConnector():
    """
    Classe principale pour interagir avec l'API FedaPay. 
    Cette classe permet de gérer les transactions, les statuts et les webhooks liés à FedaPay.
    FONCTIONNE UNIQUEMENT DANS UN CONTEXTE ASYNCHRONE
    """
    _init = False
    _instance = None  

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(FedapayConnector, cls).__new__(cls)
        return cls._instance
     
    def __init__(self, fedapay_api_url: Optional[str] = os.getenv("API_URL"), use_listen_server: Optional[bool] = False, listen_server_endpoint_name: Optional[str]=os.getenv("ENDPOINT_NAME", "webhooks"), listen_server_port: Optional[int]= 3000, fedapay_webhooks_secret_key: Optional[str]= os.getenv("FEDAPAY_AUTH_KEY"), print_log_to_console: Optional[bool]=False, save_log_to_file: Optional[bool]= True):
      
        if self._init is False:
            self._logger = initialize_logger(print_log_to_console, save_log_to_file)
            self.use_internal_listener = use_listen_server
            self.fedapay_api_url = fedapay_api_url
            self.listen_server_port = listen_server_port
            self.listen_server_endpoint_name = listen_server_endpoint_name
            self._event_manager: FedapayEvent = FedapayEvent(self._logger)
            self._payment_callback: PaymentCallback = None
            self._webhooks_callback: WebhookCallback = None
            self.accepted_transaction = ["transaction.canceled","transaction.declined","transaction.approved","transaction.deleted"]
            
            if use_listen_server is True:
                self.webhook_server = WebhookServer(logger= self._logger, endpoint= listen_server_endpoint_name, port=listen_server_port, fedapay_auth_key= fedapay_webhooks_secret_key)        
            
            self._init = True
    
    async def _init_transaction(self, setup: PaiementSetup, client_infos: UserData, montant_paiement : int, callback_url : Optional[str]= None, api_key:Optional[str]= os.getenv("API_KEY")):
        """
        Initialise une transaction avec FedaPay.

        Args:
            setup (PaiementSetup): Configuration du paiement.
            client_infos (UserData): Informations du client.
            montant_paiement (int): Montant du paiement.
            callback_url (Optional[str]): URL de rappel pour les notifications.
            api_key (Optional[str]): Clé API pour l'authentification.

        Returns:
            InitTransaction: instance du model InitTransaction
        """
        self._logger.info("Initialisation de la transaction avec FedaPay.")
        header = {"Authorization" : f"Bearer {api_key}",
                  "Content-Type": "application/json"}
        
        body = {    "description" : f"Transaction pour {client_infos.prenom} {client_infos.nom}",
                    "amount" : montant_paiement,
                    "currency" : {"iso" : get_currency(setup.pays)},
                    "callback_url" : callback_url,
                    "customer" : {
                        "firstname" : client_infos.prenom,
                        "lastname" : client_infos.nom,
                        "email" : client_infos.email,
                        "phone_number" : {
                            "number" : client_infos.tel,
                            "country" : setup.pays.value.lower()
                        }
                        }
                    }

        async with aiohttp.ClientSession(headers=header,raise_for_status=True) as session:
            async with session.post(f"{self.fedapay_api_url}/v1/transactions", json= body) as response:
                response.raise_for_status()  
                init_response = await response.json()  

        self._logger.info(f"Transaction initialisée avec succès: {init_response}")
        init_response = init_response.get("v1/transaction")

        return  InitTransaction(external_customer_id= init_response.get("external_customer_id"),
                                id_transaction= init_response.get("id"),
                                status = init_response.get("status"),
                                operation = init_response.get("operation"),)
    
    async def _get_token(self, id_transaction: int, api_key:Optional[str]= os.getenv("API_KEY")):
        """
        Récupère un token pour une transaction donnée.

        Args:
            id_transaction (int): ID de la transaction.
            api_key (Optional[str]): Clé API pour l'authentification.

        Returns:
            dict: Token et lien de paiement associés à la transaction.

        Example:
            token_data = await paiement_fedapay_class._get_token(12345)
        """
        self._logger.info(f"Récupération du token pour la transaction ID: {id_transaction}")
        header = {"Authorization" : f"Bearer {api_key}",
                  "Content-Type": "application/json"}
        
        async with aiohttp.ClientSession(headers=header,raise_for_status=True) as session:
            async with session.post(f"{self.fedapay_api_url}/v1/transactions/{id_transaction}/token" ) as response:
                response.raise_for_status()  
                data = await response.json()

        self._logger.info(f"Token récupéré avec succès: {data}")

        return GetToken(token =data.get("token"), payment_link= data.get("url"))
    
    async def _set_methode(self, client_infos: UserData, setup: PaiementSetup, token: str, api_key:Optional[str]= os.getenv("API_KEY")):
        """
        Définit la méthode de paiement pour une transaction.

        Args:
            setup (PaiementSetup): Configuration du paiement.
            token (str): Token de la transaction.
            api_key (Optional[str]): Clé API pour l'authentification.

        Returns:
            dict: Référence et statut de la méthode de paiement.

        Example:
            methode_data = await paiement_fedapay_class._set_methode(setup, "token123")
        """
        self._logger.info(f"Définition de la méthode de paiement pour le token: {token}")
        header = {"Authorization" : f"Bearer {api_key}",
                  "Content-Type": "application/json"}
        
        body = {"token" : token,
                "phone_number" : {
                    "number" : client_infos.tel,
                    "country" : setup.pays.value
                } }

        async with aiohttp.ClientSession(headers=header,raise_for_status=True) as session:
            async with session.post(f"{self.fedapay_api_url}/v1/{setup.method.name}", json = body ) as response:
                response.raise_for_status()  
                data = await response.json()
        
        self._logger.info(f"Méthode de paiement définie avec succès: {data}")
        data = data.get("v1/payment_intent")

        return {"reference":data.get("reference"),
                "status" : data.get("status")}
    
    async def _check_status(self, id_transaction:int, api_key:Optional[str]= os.getenv("API_KEY")):
        """
        Vérifie le statut d'une transaction.

        Args:
            id_transaction (int): ID de la transaction.
            api_key (Optional[str]): Clé API pour l'authentification.

        Returns:
            FedapayStatus: Instance FedapayStatus contenant statut, frais et commission de la transaction.
        """

        self._logger.info(f"Vérification du statut de la transaction ID: {id_transaction}")
        header = {"Authorization" : f"Bearer {api_key}",
                  "Content-Type": "application/json"}
        
        
        async with aiohttp.ClientSession(headers=header,raise_for_status=True) as session:
            async with session.get(f"{self.fedapay_api_url}/v1/transactions/{id_transaction}" ) as response:
                response.raise_for_status()  
                data = await response.json()
        
        self._logger.info(f"Statut de la transaction récupéré: {data}")
        data = data.get("v1/transaction")

        return FedapayStatus.model_validate({"status" : data.get("status"),
                "fedapay_commission": data.get("commission"),
                "frais" : data.get("fees") })
        
    async def _await_external_event(self, id_transaction: int, timeout_return: int):
        self._logger.info(f"Attente d'un événement externe pour la transaction ID: {id_transaction}")
        future = self._event_manager.create_future(id_transaction= id_transaction, timeout= timeout_return)
        result: EventFutureStatus = await asyncio.wait_for(future,None)
        data = self._event_manager.get_event_data(id_transaction= id_transaction)
        return result,data
    
    def _handle_payment_callback_exception(self, task: asyncio.Task):
        try:
            task.result()
        except Exception as e:
            self._logger.debug(f"Erreur dans le payment_callback : {e}", stack_info= True)

    def _handle_webhook_callback_exception(self, task: asyncio.Task):
        try:
            task.result()
        except Exception as e:
            self._logger.debug(f"Erreur dans le webhook_callback : {e}", stack_info= True)


    def start_webhook_server(self):
        """
        Démarre le serveur FastAPI pour écouter les webhooks de FedaPay dans un thread isolé n'impactant pas le thread principal de l'application
        """
        if self.use_internal_listener:
            self._logger.info(f"Démarrage du serveur FastAPI interne sur le port: {self.listen_server_port} avec pour point de terminaison: {"/"+str(self.listen_server_endpoint_name)} pour écouter les webhooks de FedaPay.")
            self.webhook_server.start_webhook_listenning(self._webhooks_callback)
        else:
            self._logger.warning("L'instance Fedapay connectore n'est pas configurée pour utiliser cette methode, passer l'argument use_listen_server a True ")

    def fedapay_save_webhook_data(self, event_dict:dict):
        """
        Méthode à utiliser dans un endpoint de l'API configuré pour recevoir les events webhook de Fedapay.
        Enregistre les données du webhook Fedapay pour une transaction donnée.

        Example:

        Vous pouvez créer un endpoint similaire pour exploiter cette methode de maniere personnalisée avec FastAPI

        @app.post(f"/webhooks", status_code=status.HTTP_200_OK)
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
                event,
                function_callback)
            
            return {"ok"}
        """

        event_model = WebhookTransaction.model_validate(event_dict)
        if not event_model.name:
            self._logger.warning("Le modèle d'événement est vide ou invalide.")
            return
        if event_model.name not in self.accepted_transaction:
            self._logger.warning(f"Please disable listenning for {event_model.name} events in the Fedapay dashboard -- just listen to {self.accepted_transaction} to be efficient")
            return
        
        self._logger.info(f"Enregistrement des données du webhook: {event_model.name}")
        is_set = self._event_manager.set_event_data(event_model)
        
        if self._webhooks_callback and is_set:
            self._logger.info("Appel de la fonction de rappel personnalisée")
            try:
                task = asyncio.create_task(self._webhooks_callback(WebhookHistory(**event_model.model_dump())))
                task.add_done_callback(self._handle_webhook_callback_exception)
            except Exception as e:
                self._logger(f"Exception Capturer au lancement du _webhooks_callback : {str(e)}")

    async def fedapay_pay(self, setup: PaiementSetup, client_infos: UserData, montant_paiement: int, api_key: Optional[str] = os.getenv("API_KEY"), callback_url: Optional[str] = None):
        """
        Effectue un paiement via FedaPay.

        Args:
            setup (PaiementSetup): Configuration du paiement, incluant le pays et la méthode de paiement.
            client_infos (UserData): Informations du client (nom, prénom, email, téléphone).
            montant_paiement (int): Montant du paiement en centimes.
            api_key (Optional[str]): Clé API pour l'authentification (par défaut, récupérée depuis les variables d'environnement).
            callback_url (Optional[str]): URL de rappel pour les notifications de transaction.

        Returns:
            FedapayPay: Instance du model FedapayPay contenan les détails de la transaction.
        """

        self._logger.info("Début du processus de paiement via FedaPay.")
        init_data = await self._init_transaction(setup= setup, api_key= api_key, client_infos= client_infos, montant_paiement= montant_paiement,  callback_url= callback_url)
        
        token_data = await self._get_token(id_transaction=init_data.id_transaction, api_key=api_key)

        status = init_data.status
        ext_ref = None

        if setup.type_paiement == TypesPaiement.SANS_REDIRECTION:

            set_methode = await self._set_methode(client_infos= client_infos, setup=setup, token=token_data.token, api_key=api_key)
            status = set_methode.get("status")
            ext_ref = set_methode.get("reference")

        self._logger.info(f"Paiement traité avec succès: {init_data.model_dump()}")

        result = FedapayPay(**init_data.model_dump(exclude= {"status"}), payment_link=token_data.payment_link,external_reference= ext_ref, status= status, montant= montant_paiement) 
        
        if self._payment_callback:
            self._logger.info(f"Appel de la fonction de rappel avec les données de paiement: {result}")
            try:
                task = asyncio.create_task(self._payment_callback(PaymentHistory(**result.model_dump())))
                task.add_done_callback(self._handle_payment_callback_exception)
            except Exception as e:
                self._logger(f"Exception Capturer au lancement du _payment_callback : {str(e)}")

        return result
    
    async def fedapay_check_transaction_status(self, id_transaction:int,api_key:Optional[str]= os.getenv("API_KEY")):
        """
        Vérifie le statut d'une transaction FedaPay.

        Args:
            id_transaction (int): ID de la transaction.
            api_key (Optional[str]): Clé API pour l'authentification.

        Returns:
            FedapayStatus: Instance FedapayStatus contenant statut, frais et commission de la transaction.
        
        Example:
            status = await paiement_fedapay_class.fedapay_check_transaction_status(12345)
        """
        self._logger.info(f"Vérification du statut de la transaction ID: {id_transaction}")
        result = await self._check_status(api_key= api_key, id_transaction= id_transaction)
        return result                  

    async def fedapay_finalise(self, id_transaction:int, api_key:Optional[str]= os.getenv("API_KEY"), timeout: Optional[int] = 600):
        """
        Finalise une transaction FedaPay.

        Args:
            id_transaction (int): ID de la transaction.
            api_key (Optional[str]): Clé API pour l'authentification.

        Returns:
            tuple: status de l'événement futur et données associées.

        Example:
            future_event_status, data = await paiement_fedapay_class.fedapay_finalise(12345)
        """
        self._logger.info(f"Finalisation de la transaction ID: {id_transaction}")
        future_event_result,data = await self._await_external_event(id_transaction,timeout)
        self._logger.info(f"Transaction finalisée: {future_event_result}")
        return future_event_result,data

    def fedapay_cancel_finalisation_waiting(self, id_transaction: int):
        return self._event_manager.cancel(id_transaction= id_transaction)
        
    def set_payment_callback_function(self, callback_function: PaymentCallback):
        if not callable(callback_function):
            raise TypeError("Callback function must be a callable")
        if not inspect.iscoroutinefunction(callback_function):
            raise TypeError("Callback function must be a async function")
        sig = inspect.signature(callback_function)
        params = list(sig.parameters.values())
        if len(params) != 1 or params[0].annotation != PaymentHistory:
            raise TypeError("Callback function must take only one argument of type PaymentHistory")
        
        self._payment_callback = callback_function

    def set_webhook_callback_function(self, callback_function: WebhookCallback):
        if not callable(callback_function):
            raise TypeError("Callback function must be a callable")
        if not inspect.iscoroutinefunction(callback_function):
            raise TypeError("Callback function must be a async function")
        sig = inspect.signature(callback_function)
        params = list(sig.parameters.values())
        if len(params) != 1 or params[0].annotation != WebhookHistory:
            raise TypeError("Callback function must take only one argument of type WebhookHistory")
        
        self._webhooks_callback = callback_function

    def cancel_all_future_event(self, reason: Optional[str] = None):
        try:
            self._event_manager.cancel_all(reason)
        except Exception as e:
            self._logger.error(f"Exception occurs cancelling all futures -- error : {e}")

    def cancel_future_event(self, transaction_id: int):
        try:
            self._event_manager.cancel(transaction_id)
        except Exception as e:
            self._logger.error(f"Exception occurs cancelling future for transaction : {transaction_id} -- error : {e}")