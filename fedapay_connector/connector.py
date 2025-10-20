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

import aiohttp
from .exceptions import (
    ConfigError,
    FedapayServerError,
    TransactionIsNotPendingAnymore,
)
from .enums import (
    EventFutureStatus,
    TypesPaiement,
    TransactionStatus,
    ExceptionOnProcessReloadBehavior,
)
from .event import FedapayEvent
from .integrations import Transactions
from .models.models import (
    PaiementSetup,
    UserData,
    PaymentHistory,
    WebhookHistory,
    WebhookTransaction,
    FedapayPay,
    ListeningProcessData,
)
from .utils import initialize_logger, validate_callback
from .types import (
    OnPersistedProcessReloadFinishedCallback,
    WebhookCallback,
    PaymentCallback,
)
from .server import WebhookServer
from typing import Dict, Optional
import os, asyncio  # noqa: E401


class FedapayConnector:
    """
    Client asynchrone Singleton pour l'API FedaPay.

    Ce connecteur est une **façade** qui implémente un pattern Singleton et gère automatiquement :
    - Les transactions et paiements FedaPay (via des appels **non bloquants**).
    - L'écoute et le traitement des webhooks.
    - La **résilience** grâce à la persistence des événements et des processus d'écoute actifs.
    - L'exécution de callbacks personnalisés lors des événements clés.

    Il fournit une **abstraction complète** des opérations FedaPay sous-jacentes pour faciliter l'intégration.

    Les appels API directs et granulaires sont exposés via la classe `Integration`
    pour ceux qui souhaitent avoir un usage plus contrôlé de leur intégration FedaPay.

    Args:
        fedapay_api_url (Optional[str]): URL de base de l'API FedaPay (ex: 'https://api.fedapay.com/v1').
        use_listen_server (Optional[bool]): Active le serveur webhook intégré (FastAPI/Uvicorn).
        listen_server_endpoint_name (Optional[str]): Nom de l'endpoint webhook (chemin URL).
        listen_server_port (Optional[int]): Port du serveur webhook.
        fedapay_webhooks_secret_key (Optional[str]): Clé secrète de signature pour la vérification des webhooks.
        print_log_to_console (Optional[bool]): Afficher les logs dans la console.
        save_log_to_file (Optional[bool]): Sauvegarder les logs dans un fichier.
        callback_timeout (Optional[float]): Délai max. d'attente pour la finalisation des tâches de callback lors de l'arrêt (`shutdown_cleanup`).
        db_url (Optional[str]): URL de connexion à la base de données pour la persistance des processus d'écoute (par défaut: SQLite).

    Note:
        La configuration utilise la hiérarchie: Arguments passés > Variables d'environnement.
        L'instance est unique (Singleton) pour toute l'application.
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
        db_url: Optional[str] = os.getenv(
            "FEDAPAY_DB_URL", "sqlite:///fedapay_connector_persisted_data/processes.db"
        ),
    ):
        if self._init is False:
            self._logger = initialize_logger(print_log_to_console, save_log_to_file)
            self.use_internal_listener = use_listen_server
            self.fedapay_api_url = fedapay_api_url

            self.default_api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY")

            self._transactions_service = Transactions(
                api_url=self.fedapay_api_url, logger=self._logger
            )

            self.listen_server_port = listen_server_port
            self.listen_server_endpoint_name = listen_server_endpoint_name

            # Contient uniquement les états terminaux d'une transaction
            self.accepted_transaction = [
                "transaction.refunded",
                "transaction.transferred",
                "transaction.canceled",
                "transaction.declined",
                "transaction.approved",
                "transaction.deleted",
                "transaction.expired",
            ]

            self._event_manager: FedapayEvent = FedapayEvent(
                self._logger,
                5,
                ExceptionOnProcessReloadBehavior.KEEP_AND_RETRY,
                self.accepted_transaction,
                db_url=db_url,
            )
            self._event_manager.set_run_at_persisted_process_reload_callback(
                callback=self._run_on_reload_callback
            )
            self._event_manager.set_run_before_timeout_callback(
                callback=self._run_on_transaction_timeout_callback
            )
            self._payment_callback: PaymentCallback = None
            self._webhooks_callback: WebhookCallback = None

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

    # ----------------------------------------
    # Callbacks
    # ----------------------------------------

    async def _run_on_reload_callback(
        self,
        data: ListeningProcessData,
    ):
        """
        Est lancé automatiquement lors du rechargement des processus d'écoute persistés au démarrage de l'application.

        Vérifie l'état actuel de la transaction auprès de FedaPay :
        - Si l'état est 'pending', l'écoute est rétablie (`reload_future`).
        - Si l'état est final (approved, declined, etc.), la Future est résolue immédiatement.

        Args:
            data (ListeningProcessData): Les données persistées de la transaction à réévaluer.

        Raises:
            asyncio.CancelledError: Si la tâche est annulée (ex: pendant l'arrêt de l'application).
            Exception: Toute erreur critique lors de l'appel API ou de la gestion interne.
        """

        try:
            transaction = (
                await self._transactions_service._get_transaction_by_fedapay_id(
                    fedapay_id=data.id_transaction, api_key=self.default_api_key
                )
            )
            if transaction.status == TransactionStatus.pending:
                # on remet l'écoute en place et on attend le timeout ou une notification de fedapay

                self._logger.info(
                    f"Attente d'un événement externe pour la transaction ID: {data.id_transaction}"
                )
                future = await self._event_manager.reload_future(
                    process_data=data, timeout=600
                )

                await self._event_manager.resolve_if_final_event_already_received(
                    data.id_transaction
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
                        name=f"transaction.{transaction.status.value}",
                        entity=transaction,
                    )
                ]

            await self._on_reload_finished_callback(result, event_data)

        except asyncio.CancelledError:
            self._logger.info(
                f"Annulation de l'attente pour la transaction {data.id_transaction} -- arret normal"
            )
            await self._event_manager.cancel(data.id_transaction)
            return EventFutureStatus.CANCELLED_INTERNALLY, None

        except Exception as e:
            self._logger.error(
                f"Erreur dans le callback de rechargement : {e}", stack_info=True
            )
            raise e

    async def _run_on_transaction_timeout_callback(self, id_transaction: int) -> bool:
        """
        Exécuté juste avant qu'une transaction n'expire. Vérifie l'état actuel de la transaction
        et tente de l'annuler (supprimer) côté FedaPay si elle est toujours 'pending'.

        Cette méthode sert de mécanisme de sécurité pour invalider les liens de paiement expirés.

        Args:
            id_transaction (int): ID de la transaction sur le point d'expirer.

        Returns:
            bool:
                - **True** si le timeout interne doit avoir lieu (transaction supprimée ou erreur critique).
                - **False** si le timeout doit être annulé et la Future résolue immédiatement (statut final trouvé).
        """

        transaction = await self._transactions_service._get_transaction_by_fedapay_id(
            fedapay_id=id_transaction, api_key=self.default_api_key
        )
        if transaction.status == TransactionStatus.pending:
            # au timeout on suprime la transaction pour qu'elle ne soit plus disponible pour le client
            try:
                resp = await self._transactions_service._delete_transaction(
                    fedapay_id=id_transaction, api_key=self.default_api_key
                )
            except aiohttp.ClientResponseError as e:
                if e.status == 403:
                    # operation non autorisée le status de la transaction a probablement changé entre temps
                    # on refresh la transaction et on resolve
                    transaction = (
                        await self._transactions_service._get_transaction_by_fedapay_id(
                            fedapay_id=id_transaction, api_key=self.default_api_key
                        )
                    )
                    await self._event_manager.set_event_data(
                        WebhookTransaction(
                            name=f"transaction.{transaction.status.value}",
                            entity=transaction,
                        )
                    )
                    return False

                else:
                    # une erreur inattendue est survenue
                    error = f"Erreur inattendue lors de la suppression de la transaction {id_transaction} -- status code: {resp.status_code} -- message: {resp.message}"
                    self._logger.error(error)
                    # l'erreur déclenchera le timeout de la transaction
                    return True

            if resp.delete_status:
                # Transaction supprimée coté fedapay
                # On peut timeout la transaction en sécurité
                return True

        else:
            # Pour une raison ou une autre on a pas recu la notification mais le status a changé
            # On ne timeout plus on resolve plutot
            # l'objet fournis sera plus leger mais contiendra le max d'infos disponible pour le reste du traitement
            await self._event_manager.set_event_data(
                WebhookTransaction(
                    name=f"transaction.{transaction.status.value}",
                    entity=transaction,
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

    # ----------------------------------------
    # Events management
    # ----------------------------------------

    async def _await_external_event(self, id_transaction: int, timeout_return: int):
        """
        Bloque l'exécution de manière asynchrone en attente d'une résolution.

        L'attente se termine soit par la réception d'une notification FedaPay (webhook),
        soit par l'expiration d'un délai interne, ou par une annulation.

        Args:
            id_transaction (int): L'ID de la transaction FedaPay surveillée.
            timeout_return (int): Le délai en secondes pour l'événement.

        Returns:
            Tuple[EventFutureStatus, Optional[Any]]: Le statut de l'événement et les données de l'événement résolu (WebhookTransaction).

        Raises:
            Exception: Toute erreur inattendue durant la création ou la résolution de la Future.
        """
        try:
            self._logger.info(
                f"Début de l'écoute d'un événement externe pour la transaction ID: {id_transaction}. Délai: {timeout_return}s."
            )

            # Crée une nouvelle Future pour cette transaction
            future = await self._event_manager.create_future(
                id_transaction=id_transaction, timeout=timeout_return
            )

            # Vérifie si le webhook est arrivé juste avant le début de l'attente
            await self._event_manager.resolve_if_final_event_already_received(
                id_transaction
            )

            # Attente bloquante. Le timeout est géré par la logique interne de self._event_manager.
            # Le second argument 'None' signifie que l'on ne veut pas un TimeoutError ici, car c'est géré en interne.
            result: EventFutureStatus = await asyncio.wait_for(future, None)

            # Récupère et efface les données de l'événement de la mémoire
            data = self._event_manager.pop_event_data(id_transaction=id_transaction)

            self._logger.info(
                f"Événement externe résolu pour {id_transaction} avec le statut: {result.name}."
            )
            return result, data

        except asyncio.CancelledError:
            self._logger.warning(
                f"Annulation asynchrone de l'attente pour la transaction {id_transaction} (Arrêt normal/Annulation utilisateur)."
            )
            await self._event_manager.cancel(id_transaction)
            return EventFutureStatus.CANCELLED_INTERNALLY, None

        except Exception as e:
            self._logger.error(
                f"Erreur fatale lors de l'attente d'événement pour {id_transaction} : {e}",
                stack_info=True,
            )
            raise e

    async def cancel_all_future_event(self, reason: Optional[str] = None):
        """
        Annule toutes les Futures d'événements FedaPay actives.

        Cette action arrête immédiatement toutes les écoutes en cours.

        Args:
            reason (Optional[str]): La raison de l'annulation (utile pour le logging).

        Raises:
            Exception: Toute erreur lors de l'accès ou de la modification de la base de données interne.
        """
        self._logger.info(
            f"Annulation de toutes les écoutes d'événements. Raison: {reason or 'Non spécifiée'}."
        )
        try:
            await self._event_manager.cancel_all(reason)
            self._logger.info("Toutes les futures ont été marquées pour annulation.")
        except Exception as e:
            self._logger.error(
                f"Exception lors de l'annulation de toutes les futures : {e}",
                stack_info=True,
            )

    async def cancel_future_event(self, transaction_id: int):
        """
        Annule l'écoute active pour une transaction spécifique.

        Ceci met fin à l'attente bloquante de la méthode `fedapay_finalise` et résout sa Future avec le statut `CANCELLED_INTERNALLY`.

        Args:
            transaction_id (int): L'ID de la transaction dont l'écoute doit être annulée.

        Raises:
            Exception: Toute erreur lors de la modification de l'état de la Future.
        """
        self._logger.info(
            f"Tentative d'annulation de l'écoute pour la transaction ID: {transaction_id}."
        )
        try:
            await self._event_manager.cancel(transaction_id)
            self._logger.info(
                f"Écoute annulée avec succès pour la transaction {transaction_id}."
            )
        except Exception as e:
            self._logger.error(
                f"Exception lors de l'annulation de la future pour la transaction {transaction_id} : {e}",
                stack_info=True,
            )

    # ----------------------------------------
    # Configuration
    # ----------------------------------------

    def set_on_persited_listening_processes_loading_finished_callback(
        self, callback: OnPersistedProcessReloadFinishedCallback
    ):
        """
        Définit le callback à appeler lorsque le chargement des processus d'écoute persistés est terminé.
        """
        validate_callback(
            callback,
            "persited_listening_processes_loading_finished callback",
        )
        if callback:
            self._on_reload_finished_callback = callback

    def set_payment_callback_function(self, callback_function: PaymentCallback):
        """
        le callback à appeler lorsqu'un nouveau paiement est initialisé (appel de fedapay_pay)
        """
        validate_callback(callback_function, "Payment callback")
        self._payment_callback = callback_function

    def set_webhook_callback_function(self, callback_function: WebhookCallback):
        """
        Définit le callback à appeler lorsque le webhook valide est reçu.
        """
        validate_callback(callback_function, "Webhook callback")

        self._webhooks_callback = callback_function

    # ----------------------------------------
    # Fedapay connector
    # ----------------------------------------

    def start_webhook_server(self):
        """
        Démarre le serveur FastAPI pour écouter les webhooks de FedaPay dans un thread isolé n'impactant pas le thread principal de l'application
        """
        if self.use_internal_listener:
            self._logger.info(
                f"Démarrage du serveur FastAPI interne sur le port: {self.listen_server_port} avec pour point de terminaison: {'/' + str(self.listen_server_endpoint_name)} pour écouter les webhooks de FedaPay."
            )
            self.webhook_server.start_webhook_listenning()
        else:
            self._logger.warning(
                "L'instance Fedapay connector n'est pas configurée pour utiliser cette methode, passer l'argument use_listen_server a True "
            )

    async def fedapay_save_webhook_data(self, event_dict: dict):
        """
        Méthode à utiliser dans un endpoint de l'API configuré pour recevoir les événements webhook de FedaPay.
        Traite, valide et sauvegarde les données d'un webhook FedaPay pour résolution ultérieure.

        Cette méthode est essentielle pour l'intégration manuelle des webhooks dans une API existante.

        Args:
            event_dict (dict): Données brutes du webhook, généralement le corps JSON de la requête POST.

        Raises:
            pydantic.ValidationError: Si le format des données du webhook est invalide.
            EventError: Si une erreur survient lors du traitement interne de l'événement.

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
        Seuls les événements configurés dans 'self.accepted_transaction' (états finaux) sont traités.
        Les callbacks configurés (`set_webhook_callback_function`) sont exécutés de façon asynchrone après l'enregistrement.
        """
        try:
            event_model = WebhookTransaction.model_validate(event_dict)
        except Exception as e:
            self._logger.error(
                f"Erreur de validation Pydantic pour les données webhook reçues : {e}"
            )
            raise e

        if not event_model.name:
            self._logger.warning(
                "Le modèle d'événement est vide ou invalide (champ 'name' manquant)."
            )
            return

        if event_model.name not in self.accepted_transaction:
            self._logger.warning(
                f"Événement {event_model.name} non surveillé. Veuillez ajuster les écoutes sur le dashboard FedaPay pour plus d'efficacité (accepter seulement: {self.accepted_transaction})."
            )
            return

        self._logger.info(
            f"Enregistrement des données du webhook pour l'événement: {event_model.name}"
        )

        is_set = await self._event_manager.set_event_data(event_model)

        if self._webhooks_callback and is_set:
            async with self._callback_lock:
                self._logger.debug("Lancement du callback personnalisé de webhook.")
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
                        f"Exception capturée au lancement du _webhooks_callback : {str(e)}"
                    )

    async def fedapay_pay(
        self,
        setup: PaiementSetup,
        client_infos: UserData | None,
        montant_paiement: int,
        callback_url: str | None = None,
        api_key: str | None = os.getenv("FEDAPAY_API_KEY"),
        merchant_reference: str | None = None,
        custom_metadata: Dict[str, str] | None = None,
        description: str | None = None,
    ):
        """
        Crée une transaction FedaPay et initie le processus de paiement.

        - Pour un paiement avec redirection, retourne le lien de paiement.
        - Pour un paiement sans redirection (ex: Mobile Money Direct), initie la demande et retourne le statut.

        Args:
            setup (PaiementSetup): Configuration du paiement (pays et méthode).
            client_infos (UserData | None): Informations du client.
            montant_paiement (int): Montant du paiement (en unités de la devise, ex: FCFA).
            callback_url (str | None): URL de rappel pour la notification de transaction.
            api_key (str | None): Clé API à utiliser, écrase la clé par défaut.
            merchant_reference (str | None): Référence unique pour le marchand.
            custom_metadata (Dict[str, str] | None): Métadonnées personnalisées.
            description (str | None): Description de la transaction.

        Returns:
            FedapayPay: Instance contenant la transaction, le token/lien, et la réponse de définition de méthode (si sans redirection).

        Raises:
            aiohttp.ClientResponseError: Erreur d'API FedaPay (ex: 400 Bad Request, 401 Unauthorized, 404 Not Found, 500 Server Error).
            ConfigError: Si une configuration essentielle est manquante.
        """
        self._logger.info(
            f"Début du processus de paiement pour un montant de {montant_paiement}."
        )

        # Utilisation de l'instance de service : self._transactions_service
        transaction_data = await self._transactions_service._create_transaction(
            setup=setup,
            client_infos=client_infos,
            montant_paiement=montant_paiement,
            api_key=api_key or self.default_api_key,
            callback_url=callback_url,
            merchant_reference=merchant_reference,
            custom_metadata=custom_metadata,
            description=description,
        )

        token_data = await self._transactions_service._get_token_and_payment_link(
            id_transaction=transaction_data.id, api_key=api_key or self.default_api_key
        )

        last_status = transaction_data.status
        set_methode = None

        if setup.type_paiement == TypesPaiement.SANS_REDIRECTION:
            set_methode = await self._transactions_service._set_payment_method(
                client_infos=client_infos,
                setup=setup,
                token=token_data.token,
                api_key=api_key or self.default_api_key,
            )
            last_status = set_methode.status

        self._logger.info(
            f"Paiement créé (ID: {transaction_data.id}) avec statut initial: {last_status}."
        )

        result = FedapayPay(
            status=last_status,
            set_methode_data=set_methode,
            transaction_data=transaction_data,
            link_and_token_data=token_data,
        )

        if self._payment_callback:
            self._logger.debug("Lancement du callback personnalisé de paiement.")
            try:
                task = asyncio.create_task(
                    self._payment_callback(PaymentHistory(**result.model_dump()))
                )
                task.add_done_callback(self._handle_payment_callback_exception)
                self._callback_tasks.add(task)
            except Exception as e:
                self._logger.error(
                    f"Exception capturée au lancement du _payment_callback : {str(e)}"
                )

        return result

    async def fedapay_get_transaction_data(
        self, id_transaction: int, api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY")
    ):
        """
        Récupère les détails complets d'une transaction FedaPay par son identifiant unique.

        Args:
            id_transaction (int): L'ID FedaPay de la transaction.
            api_key (Optional[str]): Clé API à utiliser.

        Returns:
            Transaction: L'objet Transaction complet.

        Raises:
            aiohttp.ClientResponseError: Erreur d'API (ex: 404 Not Found si l'ID est inconnu, 401 Unauthorized).
        """
        self._logger.info(f"Récupération de la transaction ID: {id_transaction}.")
        result = await self._transactions_service._get_transaction_by_fedapay_id(
            api_key=api_key or self.default_api_key, fedapay_id=id_transaction
        )
        return result

    async def fedapay_get_transaction_data_by_merchant_id(
        self, merchant_id: str, api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY")
    ):
        """
        Récupère les détails d'une transaction FedaPay en utilisant la référence marchande (`merchant_reference`).

        Args:
            merchant_id (str): La référence marchande utilisée lors de la création de la transaction.
            api_key (Optional[str]): Clé API à utiliser.

        Returns:
            Transaction: L'objet Transaction correspondant.

        Raises:
            aiohttp.ClientResponseError: Erreur d'API (ex: 404 Not Found, 401 Unauthorized).
        """
        self._logger.info(
            f"Récupération de la transaction par référence marchande: {merchant_id}."
        )
        result = (
            await self._transactions_service._get_transaction_by_merchant_reference(
                api_key=api_key or self.default_api_key, merchant_reference=merchant_id
            )
        )
        return result

    async def fedapay_finalise(
        self,
        id_transaction: int,
        timeout: Optional[int] = 600,
    ):
        """
        Bloque l'exécution et attend le résultat final d'une transaction FedaPay.

        L'attente se termine soit par la réception d'un webhook correspondant au statut final, soit par le timeout.

        Args:
            id_transaction (int): ID de la transaction à finaliser.
            timeout (Optional[int]): Délai d'attente maximum en secondes (par défaut: 600s / 10 min).

        Returns:
            tuple[EventFutureStatus, Optional[list[WebhookTransaction]]]:
                - Status de l'événement (RESOLVED, TIMEOUT, CANCELLED, CANCELLED_INTERNALLY).
                - Liste des webhooks reçus pour la résolution ou `None`.

        Raises:
            asyncio.TimeoutError: Si le timeout est dépassé et qu'aucune action n'a été résolue en interne (vérification faite).
            asyncio.CancelledError: Si l'attente est annulée de l'extérieur.
            ConfigError: Si une configuration API interne est invalide.
            Exception: Toute erreur inattendue durant la création ou la résolution de la Future.

        Note:
        Une vérification de l'état est effectuée automatiquement en interne à la fin du timeout pour garantir l'état le plus récent.
        """
        self._logger.info(
            f"Début de la finalisation bloquante pour la transaction ID: {id_transaction}. Timeout: {timeout}s."
        )
        future_event_result, data = await self._await_external_event(
            id_transaction, timeout
        )
        self._logger.info(
            f"Finalisation de la transaction {id_transaction} terminée avec le statut: {future_event_result.name}."
        )
        return future_event_result, data

    async def fedapay_cancel_transaction(
        self, id_transaction: int, api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY")
    ):
        """
        Tente de supprimer (annuler) une transaction FedaPay si elle est toujours en attente (`pending`).

        Si la suppression réussit, l'écoute locale pour cette transaction est également annulée.

        Args:
            id_transaction (int): ID de la transaction à annuler.
            api_key (Optional[str]): Clé API à utiliser.

        Returns:
            TransactionDeleteStatus: Objet indiquant le statut de la tentative de suppression.

        Raises:
            TransactionIsNotPendingAnymore: Si la transaction ne peut pas être supprimée (ex: déjà approuvée ou terminée).
            ClientResponseError: Si une erreur d'API inattendue survient lors de la tentative de suppression.
        """
        self._logger.info(
            f"Tentative de suppression de la transaction ID: {id_transaction}."
        )

        try:
            result = await self._transactions_service._delete_transaction(
                fedapay_id=id_transaction, api_key=api_key or self.default_api_key
            )

            if result.delete_status:
                self._logger.info(
                    f"Transaction avec l'id {id_transaction} supprimée avec succès (statut: {result.status_code})."
                )
                await self._event_manager.cancel(id_transaction=id_transaction)
                self._logger.info(
                    f"Écoute interne pour la transaction {id_transaction} annulée."
                )
            return result
        except aiohttp.ClientResponseError as e:
            if e.status == 403:
                error = f"La transaction {id_transaction} ne peut être supprimée (statut final ou non autorisé, code: 403)."
                self._logger.warning(error)
                raise TransactionIsNotPendingAnymore(e)
            else:
                error = f"Erreur inattendue lors de la suppression de la transaction {id_transaction} -- code: {e.status} -- message: {e.message}"
                self._logger.error(error)
                raise e

    async def load_persisted_listening_processes(self):
        """
        Charge les processus d'écoute (futures d'événements) persistés depuis la base de données locale.

        Cette méthode est critique pour rétablir la continuité de service et les écoutes perdues lors d'un
        redémarrage de l'application. Elle doit être appelée explicitement au démarrage.

        Raises:
            ConfigError: Si le callback de fin de chargement (`_on_reload_finished_callback`) n'a pas été défini.
                        Ce callback est nécessaire pour traiter les transactions au moment du rechargement.
        """
        self._logger.info("Tentative de chargement des processus d'écoute persistés.")

        if not self._on_reload_finished_callback:
            error_msg = "Le callback de fin de chargement n'est pas défini. Appelez 'set_on_persited_listening_processes_loading_finished_callback' avant d'appeler cette méthode."
            self._logger.error(error_msg)
            raise ConfigError(error_msg)

        await self._event_manager.load_persisted_processes()
        self._logger.info(
            "Chargement des processus d'écoute terminé. Les callbacks de rechargement sont maintenant en cours d'exécution."
        )

    async def shutdown_cleanup(self):
        """
        Nettoie proprement toutes les ressources asynchrones avant l'arrêt de l'application.

        Effectue les étapes suivantes dans l'ordre sécurisé :
        1. Annule toutes les futures d'événements en attente (`fedapay_finalise`).
        2. Attend l'achèvement des tâches de callback en cours (`_payment_callback`, `_webhooks_callback`) avec un délai (`self.callback_timeout`).
        3. Arrête le serveur webhook FastAPI interne (si actif).

        Raises:
            Exception: Toute erreur survenant pendant le nettoyage est capturée, loguée, mais l'arrêt se poursuit pour assurer la fermeture de l'application.

        Note:
            Cette méthode **doit** être appelée par le gestionnaire d'événements de l'application (ex: signal SIGTERM, événement d'arrêt FastAPI/Aiohttp) pour garantir la continuité des processus persistés.
        """
        async with self._cleanup_lock:
            try:
                self._logger.info(
                    "Début du processus de nettoyage et d'arrêt ordonné du FedapayConnector."
                )

                # 1. Annulation de tous les futures en attente
                await self._event_manager.cancel_all("Application shutdown cleanup")
                self._logger.debug(
                    "Toutes les écoutes d'événements FedaPay ont été annulées."
                )

                # 2. Attente des callbacks en cours d'exécution avec timeout
                if self._callback_tasks:
                    pending = list(self._callback_tasks)
                    self._logger.info(
                        f"Attente de {len(pending)} tâches de callback en cours d'exécution (timeout: {self.callback_timeout}s)."
                    )
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(*pending, return_exceptions=True),
                            timeout=self.callback_timeout,
                        )
                        self._logger.info(
                            "Toutes les tâches de callback ont été terminées dans le temps imparti."
                        )
                    except asyncio.TimeoutError:
                        self._logger.warning(
                            f"Timeout ({self.callback_timeout}s) pendant l'attente des callbacks. Les tâches restantes seront annulées."
                        )
                    finally:
                        # Annuler les tâches restantes
                        for task in pending:
                            if not task.done():
                                task.cancel()
                        self._callback_tasks.clear()

                # 3. Arrêt du serveur webhook en dernier
                if self.use_internal_listener:
                    self._logger.info("Arrêt du serveur webhook interne.")
                    try:
                        self.webhook_server.stop_webhook_listenning()
                        self._logger.debug("Le serveur webhook interne a été arrêté.")
                    except Exception as e:
                        self._logger.error(
                            f"Erreur lors de l'arrêt du serveur webhook : {e}",
                            exc_info=True,
                        )

            except Exception as e:
                # Cette exception capture toute erreur non gérée dans les blocs précédents
                self._logger.critical(
                    f"Erreur CRITIQUE pendant le nettoyage final : {e}", exc_info=True
                )
