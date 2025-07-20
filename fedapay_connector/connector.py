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

from .exceptions import ConfigError
from .enums import (
    EventFutureStatus,
    TypesPaiement,
    TransactionStatus,
    ExceptionOnProcessReloadBehavior,
)
from .event import FedapayEvent
from .models import (
    FedapayStatus,
    PaiementSetup,
    UserData,
    PaymentHistory,
    WebhookHistory,
    WebhookTransaction,
    InitTransaction,
    FedapayPay,
    GetToken,
    ListeningProcessData,
    Transaction,
)
from .utils import initialize_logger, get_currency, validate_callback
from .types import (
    OnPersistedProcessReloadFinishedCallback,
    WebhookCallback,
    PaymentCallback,
)
from .server import WebhookServer
from typing import Optional
import os, asyncio, aiohttp  # noqa: E401


class FedapayConnector:
    """
    Client asynchrone pour l'API FedaPay.

    Ce client implémente un pattern Singleton et gère automatiquement :
    - Les paiements FedaPay
    - Les webhooks
    - La persistence des événements
    - Les callbacks personnalisés

    Args:
        fedapay_api_url (Optional[str]): URL de l'API FedaPay
        use_listen_server (Optional[bool]): Utiliser le serveur webhook intégré
        listen_server_endpoint_name (Optional[str]): Nom de l'endpoint webhook
        listen_server_port (Optional[int]): Port du serveur webhook
        fedapay_webhooks_secret_key (Optional[str]): Clé secrète webhook
        print_log_to_console (Optional[bool]): Afficher les logs dans la console
        save_log_to_file (Optional[bool]): Sauvegarder les logs dans un fichier
        callback_timeout (Optional[float]): Délai d'attente pour la finalisation de l'exécution des callbacks lors de l'arrêt de l'application

    Note:
        Les variables d'environnement peuvent être utilisées pour la configuration
    """

    _init = False
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(FedapayConnector, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        fedapay_api_url: Optional[str] = os.getenv("FEDAPAY_API_URL"),
        use_listen_server: Optional[bool] = False,
        listen_server_endpoint_name: Optional[str] = os.getenv(
            "FEDAPAY_ENDPOINT_NAME", "webhooks"
        ),
        listen_server_port: Optional[int] = 3000,
        fedapay_webhooks_secret_key: Optional[str] = os.getenv("FEDAPAY_AUTH_KEY"),
        print_log_to_console: Optional[bool] = False,
        save_log_to_file: Optional[bool] = True,
        callback_timeout: Optional[float] = 10,
    ):
        if self._init is False:
            self._logger = initialize_logger(print_log_to_console, save_log_to_file)
            self.use_internal_listener = use_listen_server
            self.fedapay_api_url = fedapay_api_url
            self.listen_server_port = listen_server_port
            self.listen_server_endpoint_name = listen_server_endpoint_name
            self._event_manager: FedapayEvent = FedapayEvent(
                self._logger, 5, ExceptionOnProcessReloadBehavior.KEEP_AND_RETRY
            )
            self._event_manager.set_run_at_persisted_process_reload_callback(
                callback=self._run_on_reload_callback
            )
            self._event_manager.set_run_before_timeout_callback(
                callback=self._run_on_transaction_timeout_callback
            )
            self._payment_callback: PaymentCallback = None
            self._webhooks_callback: WebhookCallback = None
            self.accepted_transaction = [
                "transaction.canceled",
                "transaction.declined",
                "transaction.approved",
                "transaction.deleted",
            ]

            if use_listen_server is True:
                self.webhook_server = WebhookServer(
                    logger=self._logger,
                    endpoint=listen_server_endpoint_name,
                    port=listen_server_port,
                    fedapay_auth_key=fedapay_webhooks_secret_key,
                )

            self._on_reload_finished_callback: Optional[
                OnPersistedProcessReloadFinishedCallback
            ] = None
            self._callback_lock = asyncio.Lock()
            self._cleanup_lock = asyncio.Lock()
            self._callback_tasks = set()
            self.callback_timeout = callback_timeout

            self._init = True

    async def _init_transaction(
        self,
        setup: PaiementSetup,
        client_infos: UserData,
        montant_paiement: int,
        callback_url: Optional[str] = None,
        api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY"),
    ):
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
        header = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "description": f"Transaction pour {client_infos.prenom} {client_infos.nom}",
            "amount": montant_paiement,
            "currency": {"iso": get_currency(setup.pays)},
            "callback_url": callback_url,
            "customer": {
                "firstname": client_infos.prenom,
                "lastname": client_infos.nom,
                "email": client_infos.email,
                "phone_number": {
                    "number": client_infos.tel,
                    "country": setup.pays.value.lower(),
                },
            },
        }

        async with aiohttp.ClientSession(
            headers=header, raise_for_status=True
        ) as session:
            async with session.post(
                f"{self.fedapay_api_url}/v1/transactions", json=body
            ) as response:
                response.raise_for_status()
                init_response = await response.json()

        self._logger.info(f"Transaction initialisée avec succès: {init_response}")
        init_response = init_response.get("v1/transaction")

        return InitTransaction(
            external_customer_id=init_response.get("external_customer_id"),
            id_transaction=init_response.get("id"),
            status=init_response.get("status"),
            operation=init_response.get("operation"),
        )

    async def _get_token(
        self, id_transaction: int, api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY")
    ):
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
        self._logger.info(
            f"Récupération du token pour la transaction ID: {id_transaction}"
        )
        header = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession(
            headers=header, raise_for_status=True
        ) as session:
            async with session.post(
                f"{self.fedapay_api_url}/v1/transactions/{id_transaction}/token"
            ) as response:
                response.raise_for_status()
                data = await response.json()

        self._logger.info(f"Token récupéré avec succès: {data}")

        return GetToken(token=data.get("token"), payment_link=data.get("url"))

    async def _set_methode(
        self,
        client_infos: UserData,
        setup: PaiementSetup,
        token: str,
        api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY"),
    ):
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
        self._logger.info(
            f"Définition de la méthode de paiement pour le token: {token}"
        )
        header = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "token": token,
            "phone_number": {"number": client_infos.tel, "country": setup.pays.value},
        }

        async with aiohttp.ClientSession(
            headers=header, raise_for_status=True
        ) as session:
            async with session.post(
                f"{self.fedapay_api_url}/v1/{setup.method.name}", json=body
            ) as response:
                response.raise_for_status()
                data = await response.json()

        self._logger.info(f"Méthode de paiement définie avec succès: {data}")
        data = data.get("v1/payment_intent")

        return {"reference": data.get("reference"), "status": data.get("status")}

    async def _check_status(
        self, id_transaction: int, api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY")
    ):
        """
        Vérifie le statut d'une transaction.

        Args:
            id_transaction (int): ID de la transaction.
            api_key (Optional[str]): Clé API pour l'authentification.

        Returns:
            FedapayStatus: Instance FedapayStatus contenant statut, frais et commission de la transaction.
        """

        self._logger.info(
            f"Vérification du statut de la transaction ID: {id_transaction}"
        )
        header = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession(
            headers=header, raise_for_status=True
        ) as session:
            async with session.get(
                f"{self.fedapay_api_url}/v1/transactions/{id_transaction}"
            ) as response:
                response.raise_for_status()
                data = await response.json()

        self._logger.info(f"Statut de la transaction récupéré: {data}")
        data = data.get("v1/transaction")

        return FedapayStatus.model_validate(
            {
                "status": data.get("status"),
                "fedapay_commission": data.get("commission"),
                "frais": data.get("fees"),
            }
        )

    async def _await_external_event(self, id_transaction: int, timeout_return: int):
        try:
            self._logger.info(
                f"Attente d'un événement externe pour la transaction ID: {id_transaction}"
            )
            future = await self._event_manager.create_future(
                id_transaction=id_transaction, timeout=timeout_return
            )
            result: EventFutureStatus = await asyncio.wait_for(future, None)
            data = self._event_manager.pop_event_data(id_transaction=id_transaction)
            return result, data
        except asyncio.CancelledError:
            self._logger.info(
                f"Annulation de l'attente pour la transaction {id_transaction} -- arret normal"
            )
            await self._event_manager.cancel(id_transaction)
            return EventFutureStatus.CANCELLED, None
        except Exception as e:
            self._logger.error(
                f"Erreur dans le callback de rechargement : {e}", stack_info=True
            )
            raise e

    async def _run_on_reload_callback(self, data: ListeningProcessData):
        try:
            status = await self._check_status(id_transaction=data.id_transaction)
            if (
                status.status == TransactionStatus.created
                or status.status == TransactionStatus.pending
            ):
                # on remet l'écoute en place et on attend le timeout ou une notification de fedapay

                self._logger.info(
                    f"Attente d'un événement externe pour la transaction ID: {data.id_transaction}"
                )
                future = await self._event_manager.reload_future(
                    process_data=data, timeout=600
                )
                result: EventFutureStatus = await asyncio.wait_for(future, None)
                event_data = self._event_manager.pop_event_data(
                    id_transaction=data.id_transaction
                )
            else:
                result = EventFutureStatus.RESOLVED
                event_data = [
                    # on aura pas un model complet avec les données fournies par fedapay
                    # mais les information contenues dans le model partiel devraient etre suffisantes pour tout traitement plus tard.
                    WebhookTransaction(
                        name=f"transaction.{status.status.value}",
                        entity=Transaction(
                            id=data.id_transaction,
                            status=status.status,
                            fees=status.frais,
                            commission=status.fedapay_commission,
                        ),
                    )
                ]

            await self._on_reload_finished_callback(result, event_data)

        except asyncio.CancelledError:
            self._logger.info(
                f"Annulation de l'attente pour la transaction {data.id_transaction} -- arret normal"
            )
            await self._event_manager.cancel(data.id_transaction)
            return EventFutureStatus.CANCELLED, None

        except Exception as e:
            self._logger.error(
                f"Erreur dans le callback de rechargement : {e}", stack_info=True
            )
            raise e

    async def _run_on_transaction_timeout_callback(self, id_transaction: int):
        status = await self._check_status(id_transaction=id_transaction)
        if (
            status.status == TransactionStatus.created
            or status.status == TransactionStatus.pending
        ):
            # idéalement faire un appel a fedapay pour cloturer la transaction puis timeout en interne
            # pour que si la page de aiement est tjr dispo dans un client elle ne puisse plus traiter un paiment pour etre
            # sûr de ne pas recevoir un paiement intraçable et innatendu
            # pas encore trouver une methode pour invalider ou cancel le paiment userside à part la supression complete
            # que je ne trouve pas super interessant donc on va attendre simplement
            # que la transaction tombe en expiration automatiquement coté fedapay
            return True
        else:
            # au lieu de timeout on resolve parce que suite a un pb ou un autre on a pas recu la notif de fedapay pour l'event
            # ainsi on va peut etre attendre tout le temps du timeout avant de resolve mais au aura quand meme resolve tard au lieu de jamais
            # systeme mis en place pour lisser les delais de reponse de fedapay ou les pannes empechant l'envois de notifications d'event.
            await self._event_manager.set_event_data(
                WebhookTransaction(
                    name=f"transaction.{status.status.value}",
                    entity=Transaction(
                        id=id_transaction,
                        status=status.status,
                        fees=status.frais,
                        commission=status.fedapay_commission,
                    ),
                )
            )
            return False

    def _handle_payment_callback_exception(self, task: asyncio.Task):
        try:
            task.result()
        except Exception as e:
            self._logger.error(
                f"Erreur dans le payment_callback : {e}", stack_info=True
            )
        finally:
            self._callback_tasks.discard(task)

    def _handle_webhook_callback_exception(self, task: asyncio.Task):
        try:
            task.result()
        except Exception as e:
            self._logger.debug(
                f"Erreur dans le webhook_callback : {e}", stack_info=True
            )
        finally:
            self._callback_tasks.discard(task)

    def start_webhook_server(self):
        """
        Démarre le serveur FastAPI pour écouter les webhooks de FedaPay dans un thread isolé n'impactant pas le thread principal de l'application
        """
        if self.use_internal_listener:
            self._logger.info(
                f"Démarrage du serveur FastAPI interne sur le port: {self.listen_server_port} avec pour point de terminaison: {'/' + str(self.listen_server_endpoint_name)} pour écouter les webhooks de FedaPay."
            )
            self.webhook_server.start_webhook_listenning(self._webhooks_callback)
        else:
            self._logger.warning(
                "L'instance Fedapay connector n'est pas configurée pour utiliser cette methode, passer l'argument use_listen_server a True "
            )

    async def fedapay_save_webhook_data(self, event_dict: dict):
        """
        Méthode à utiliser dans un endpoint de l'API configuré pour recevoir les events webhook de Fedapay.
        Traite et sauvegarde les données d'un webhook FedaPay.

        Cette méthode est utilisée pour intégrer les webhooks dans une API existante.

        Args:
            event_dict (dict): Données brutes du webhook

        Raises:
            ValidationError: Format de données invalide
            EventError: Erreur de traitement de l'événement

        Example:

        Vous pouvez créer un endpoint similaire pour exploiter cette methode de maniere personnalisée avec FastAPI

        @router.post(
            f"{os.getenv('FEDAPAY_ENDPOINT_NAME', 'webhooks')}", status_code=status.HTTP_200_OK
        )
        async def receive_webhooks(request: Request):
            header = request.headers
            agregateur = str(header.get("agregateur"))
            payload = await request.body()
            fd = fedapay_connector.FedapayConnector(use_listen_server=False)

            if not agregateur == "Fedapay":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Accès refusé",
                )

            fedapay_connector.utils.verify_signature(
                payload, header.get("x-fedapay-signature"), os.getenv("FEDAPAY_AUTH_KEY")
            )
            event = await request.json()
            fd.fedapay_save_webhook_data(event)

            return {"ok"}

        Note:
        Seuls les événements configurés dans accepted_transaction sont traités
        Les callbacks configurés sont exécutés de façon asynchrone

        """

        event_model = WebhookTransaction.model_validate(event_dict)
        if not event_model.name:
            self._logger.warning("Le modèle d'événement est vide ou invalide.")
            return
        if event_model.name not in self.accepted_transaction:
            self._logger.warning(
                f"Please disable listenning for {event_model.name} events in the Fedapay dashboard -- just listen to {self.accepted_transaction} to be efficient"
            )
            return

        self._logger.info(f"Enregistrement des données du webhook: {event_model.name}")

        is_set = await self._event_manager.set_event_data(event_model)

        if self._webhooks_callback and is_set:
            async with self._callback_lock:
                self._logger.info("Appel de la fonction de rappel personnalisée")
                try:
                    task = asyncio.create_task(
                        self._webhooks_callback(
                            WebhookHistory(**event_model.model_dump())
                        )
                    )
                    self._callback_tasks.add(task)
                    task.add_done_callback(self._handle_webhook_callback_exception)
                except Exception as e:
                    self._logger.error(
                        f"Exception Capturer au lancement du _webhooks_callback : {str(e)}"
                    )

    async def fedapay_pay(
        self,
        setup: PaiementSetup,
        client_infos: UserData,
        montant_paiement: int,
        api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY"),
        callback_url: Optional[str] = None,
    ):
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

        Raises:
            ConfigError: Configuration invalide
            APIError: Erreur API FedaPay
        """

        self._logger.info("Début du processus de paiement via FedaPay.")
        init_data = await self._init_transaction(
            setup=setup,
            api_key=api_key,
            client_infos=client_infos,
            montant_paiement=montant_paiement,
            callback_url=callback_url,
        )

        token_data = await self._get_token(
            id_transaction=init_data.id_transaction, api_key=api_key
        )

        status = init_data.status
        ext_ref = None

        if setup.type_paiement == TypesPaiement.SANS_REDIRECTION:
            set_methode = await self._set_methode(
                client_infos=client_infos,
                setup=setup,
                token=token_data.token,
                api_key=api_key,
            )
            status = set_methode.get("status")
            ext_ref = set_methode.get("reference")

        self._logger.info(f"Paiement traité avec succès: {init_data.model_dump()}")

        result = FedapayPay(
            **init_data.model_dump(exclude={"status"}),
            payment_link=token_data.payment_link,
            external_reference=ext_ref,
            status=status,
            montant=montant_paiement,
        )

        if self._payment_callback:
            self._logger.info(
                f"Appel de la fonction de rappel avec les données de paiement: {result}"
            )
            try:
                task = asyncio.create_task(
                    self._payment_callback(PaymentHistory(**result.model_dump()))
                )
                task.add_done_callback(self._handle_payment_callback_exception)
                self._callback_tasks.add(task)
            except Exception as e:
                self._logger.error(
                    f"Exception Capturer au lancement du _payment_callback : {str(e)}"
                )

        return result

    async def fedapay_check_transaction_status(
        self, id_transaction: int, api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY")
    ):
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
        self._logger.info(
            f"Vérification du statut de la transaction ID: {id_transaction}"
        )
        result = await self._check_status(
            api_key=api_key, id_transaction=id_transaction
        )
        return result

    async def fedapay_finalise(
        self,
        id_transaction: int,
        timeout: Optional[int] = 600,
    ):
        """
        Finalise et attend le résultat d'une transaction FedaPay.

        Attend la réception d'un webhook ou le timeout pour une transaction donnée.

        Args:
            id_transaction (int): ID de la transaction à finaliser
            timeout (Optional[int]): Délai d'attente maximum en secondes

        Returns:
            tuple[EventFutureStatus, Optional[list[WebhookTransaction]]]:
                - Status de l'événement (RESOLVED, TIMEOUT, CANCELLED)
                - Liste des webhooks reçus ou None

        Raises:
            ConfigError: Configuration API invalide
            TimeoutError: Délai d'attente dépassé
            CancelledError: Attente annulée

        Note:
            Le timeout par défaut est de 600 secondes (10 minutes)
            Une vérification manuelle est faites à la fin de chaque timeout automatiquement en interne
            donc si vous recever un timeout c'est que rien ne s'est vraiment passé
        """

        self._logger.info(f"Finalisation de la transaction ID: {id_transaction}")
        future_event_result, data = await self._await_external_event(
            id_transaction, timeout
        )
        self._logger.info(f"Transaction finalisée: {future_event_result}")
        return future_event_result, data

    async def fedapay_cancel_finalisation_waiting(self, id_transaction: int):
        """
        Annule l'attente de finalisation d'une transaction FedaPay.

        Args:
            id_transaction (int): ID de la transaction à annuler

        """
        return await self._event_manager.cancel(id_transaction=id_transaction)

    def set_on_persited_listening_processes_loading_finished_callback(
        self, callback: OnPersistedProcessReloadFinishedCallback
    ):
        """
        Définit le callback à appeler lorsque le chargement des processus d'écoute persistés est terminé.
        """
        validate_callback(
            callback,
            {
                "future_event_status": EventFutureStatus,
                "data": list[WebhookTransaction] | None,
            },
            "persited_listening_processes_loading_finished callback",
        )
        if callback:
            self._on_reload_finished_callback = callback

    async def load_persisted_listening_processes(self):
        """
        Charge les processus d'écoute persistés depuis la base de données.
        Doit être appelé explicitement au démarrage de l'application si
        vous souhaitez rétablir les potentielles écoutes perdues lors du dernier redémarrage de l'application
        """
        if not self._on_reload_finished_callback:
            raise ConfigError(
                "Callback not set - Call 'set_on_persited_listening_processes_loading_finished_callback' before to set it and retry"
            )
        await self._event_manager.load_persisted_processes()

    def set_payment_callback_function(self, callback_function: PaymentCallback):
        """
        le callback à appeler lorsqu'un nouveau paiement est initialisé (appel de fedapay_pay)
        """
        validate_callback(
            callback_function, {"payment": PaymentHistory}, "Payment callback"
        )
        self._payment_callback = callback_function

    def set_webhook_callback_function(self, callback_function: WebhookCallback):
        """
        Définit le callback à appeler lorsque le webhook valide est reçu.
        """
        validate_callback(
            callback_function, {"webhook_data": WebhookHistory}, "Webhook callback"
        )

        self._webhooks_callback = callback_function

    async def cancel_all_future_event(self, reason: Optional[str] = None):
        """
        Annule toutes les écoutes actives.
        """
        try:
            await self._event_manager.cancel_all(reason)
        except Exception as e:
            self._logger.error(
                f"Exception occurs cancelling all futures -- error : {e}"
            )

    async def cancel_future_event(self, transaction_id: int):
        """
        Anulle l'écoute active pour la transaction.

        Args:
            transaction_id (int): L'ID de la transaction à annuler.
        """

        try:
            await self._event_manager.cancel(transaction_id)
        except Exception as e:
            self._logger.error(
                f"Exception occurs cancelling future for transaction : {transaction_id} -- error : {e}"
            )

    async def shutdown_cleanup(self):
        """
        Nettoie proprement les ressources avant l'arrêt.

        Effectue dans l'ordre:
        1. Annulation de tous les futures en attente
        2. Attente des callbacks en cours d'exécution avec timeout
        3. Arrêt du serveur webhook si actif

        Raises:
            Exception: Une erreur durant le nettoyage
            Toute exception est capturée et loggée

        Note:
            Cette méthode doit être appelée avant l'arrêt de l'application
        """
        async with self._cleanup_lock:
            try:
                # D'abord annuler tous les futures
                await self.cancel_all_future_event("Application shutdown")

                # Attendre les callbacks avec timeout
                if self._callback_tasks:
                    pending = list(self._callback_tasks)
                    self._logger.info(f"Attente de {len(pending)} tâches de callback")
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(*pending, return_exceptions=True),
                            timeout=self.callback_timeout,
                        )
                    except asyncio.TimeoutError:
                        self._logger.warning("Timeout pendant l'attente des callbacks")
                    finally:
                        # Annuler les tâches restantes
                        for task in pending:
                            if not task.done():
                                task.cancel()
                        self._callback_tasks.clear()

                # Arrêter le serveur webhook en dernier
                if self.use_internal_listener:
                    self._logger.info("Arrêt du serveur webhook interne")
                    try:
                        self.webhook_server.stop_webhook_listenning()
                    except Exception as e:
                        self._logger.error(
                            f"Erreur lors de l'arrêt du serveur webhook: {e}"
                        )

            except Exception as e:
                self._logger.error(f"Erreur pendant le nettoyage: {e}", exc_info=True)
