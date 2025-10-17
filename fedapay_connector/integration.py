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

import logging
import os
from typing import Optional, Dict, Any

from fedapay_connector import utils
from fedapay_connector.models import (
    PaiementSetup,
    Transaction,
    TransactionDeleteStatus,
    TransactionListResponse,
    TransactionPaymentMethodResponse,
    TransactionToken,
    BalanceListResponse,
    BalanceResponse,
    CurrencyListResponse,
    CurrencyResponse,
    EventListResponse,
    EventResponse,
    LogListResponse,
    LogResponse,
    UserData,
    WebhookListResponse,
    WebhookResponse,
)
from .integrations import Transactions, Balances, Currencies, Events, Logs, Webhooks


class Integration:
    """
    Façade principale pour interagir avec l'API FedaPay.

    Cette classe simplifie l'accès à toutes les fonctionnalités (Transactions, Soldes, Webhooks, etc.)
    en un seul point d'entrée. Elle permet aux utilisateurs avancés de gérer manuellement
    le cycle de vie complet des ressources FedaPay (CRUD) sans passer par les workflows automatiques
    du connecteur.
    """

    def __init__(
        self,
        api_url: str = os.getenv("FEDAPAY_API_URL"),
        logger: logging.Logger = None,
        default_api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY"),
    ):
        """
        Initialise le connecteur d'intégration FedaPay.

        Args:
            api_url (str): L'URL de base de l'API FedaPay (par défaut, lue depuis FEDAPAY_API_URL).
            logger: Instance de logger pour l'enregistrement des événements. Par défaut, un logger standard est initialisé.
            default_api_key (Optional[str]): Clé API par défaut à utiliser si non spécifiée dans les méthodes.

        Raises:
            ValueError: Si `api_url` ou `default_api_key` ne sont pas fournis.
        """
        if not api_url:
            raise ValueError(
                "L'URL de l'API FedaPay (FEDAPAY_API_URL) doit être fournie ou configurer en variable d'environnement"
            )

        if not default_api_key:
            raise ValueError(
                "Le token d'acces de l'API FedaPay (FEDAPAY_API_KEY) doit être fournie ou configurer en variable d'environnement"
            )

        self.fedapay_api_url = api_url
        self._logger = logger or utils.initialize_logger()
        self.default_api_key = default_api_key

        # Initialisation des classes de service
        self._transactions_service = Transactions(
            api_url=self.fedapay_api_url, logger=self._logger
        )
        self._balances_service = Balances(
            api_url=self.fedapay_api_url, logger=self._logger
        )
        self._currencies_service = Currencies(
            api_url=self.fedapay_api_url, logger=self._logger
        )
        self._events_service = Events(api_url=self.fedapay_api_url, logger=self._logger)
        self._logs_service = Logs(api_url=self.fedapay_api_url, logger=self._logger)
        self._webhooks_service = Webhooks(
            api_url=self.fedapay_api_url, logger=self._logger
        )

    # ----------------------------------------
    # FAÇADE : Transactions
    # ----------------------------------------

    async def get_all_transactions(
        self,
        params: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None,
    ) -> TransactionListResponse:
        """
        Récupère la liste paginée de toutes les transactions du compte marchand.

        Args:
            params (Optional[Dict[str, Any]]): Paramètres de requête pour le filtrage et la pagination (ex: {'status': 'approved', 'page': 2}).
            api_key (Optional[str]): Clé API à utiliser pour cet appel, écrase la clé par défaut si fournie.

        Returns:
            TransactionListResponse: Une liste d'objets Transaction et les métadonnées de pagination.
        """
        return await self._transactions_service._get_all_transactions(
            params=params, api_key=api_key or self.default_api_key
        )

    async def get_transaction_by_fedapay_id(
        self, fedapay_id: str, api_key: Optional[str] = None
    ) -> Transaction:
        """
        Récupère une transaction unique par son ID FedaPay.

        Args:
            fedapay_id (str): L'identifiant unique de la transaction.
            api_key (Optional[str]): Clé API à utiliser.

        Returns:
            Transaction: L'objet Transaction complet.
        """
        return await self._transactions_service._get_transaction_by_fedapay_id(
            fedapay_id=fedapay_id, api_key=api_key or self.default_api_key
        )

    async def get_transaction_by_merchant_reference(
        self, merchant_reference: str, api_key: Optional[str] = None
    ) -> Transaction:
        """
        Récupère une transaction unique par sa référence marchande (`merchant_reference`).

        Args:
            merchant_reference (str): La référence fournie par le marchand lors de la création de la transaction.
            api_key (Optional[str]): Clé API à utiliser.

        Returns:
            Transaction: L'objet Transaction correspondant à la référence.
        """
        return await self._transactions_service._get_transaction_by_merchant_reference(
            merchant_reference=merchant_reference,
            api_key=api_key or self.default_api_key,
        )

    async def update_transaction(
        self,
        fedapay_id: str,
        data_to_update: Dict[str, Any],
        api_key: Optional[str] = None,
    ) -> Transaction:
        """
        Met à jour les informations modifiables d'une transaction (ex: description, custom_metadata).

        Args:
            fedapay_id (str): L'identifiant unique de la transaction à mettre à jour.
            data_to_update (Dict[str, Any]): Dictionnaire des champs à modifier (ex: {'description': 'Nouvelle description'}).
            api_key (Optional[str]): Clé API à utiliser.

        Returns:
            Transaction: L'objet Transaction mis à jour.
        """
        return await self._transactions_service._update_transaction(
            fedapay_id=fedapay_id,
            data_to_update=data_to_update,
            api_key=api_key or self.default_api_key,
        )

    async def delete_transaction(
        self, fedapay_id: str, api_key: Optional[str] = None
    ) -> TransactionDeleteStatus:
        """
        Annule et supprime définitivement une transaction par son ID.

        Args:
            fedapay_id (str): L'identifiant unique de la transaction à annuler.
            api_key (Optional[str]): Clé API à utiliser.

        Returns:
            TransactionDeleteStatus: Statut de l'opération de suppression (succès ou échec avec message).
        """
        return await self._transactions_service._delete_transaction(
            fedapay_id=fedapay_id, api_key=api_key or self.default_api_key
        )

    async def create_transaction(
        self,
        setup: PaiementSetup,
        client_infos: UserData | None,
        montant_paiement: int,
        callback_url: str | None = None,
        api_key: str | None = os.getenv("FEDAPAY_API_KEY"),
        merchant_reference: str | None = None,
        custom_metadata: Dict[str, str] | None = None,
        description: str | None = None,
    ) -> Transaction:
        """
        Crée une nouvelle transaction sur l'API FedaPay.

        Note: L'attribut `description` semble être une faute de frappe pour `description`
        dans la fonction interne. Veuillez vérifier.

        Args:
            setup (PaiementSetup): Configuration du pays et du mode de paiement.
            client_infos (UserData | None): Informations détaillées du client.
            montant_paiement (int): Montant total à payer (en unités de la devise, ex: FCFA).
            callback_url (str | None): URL où FedaPay enverra les notifications de statut.
            api_key (str | None): Clé API à utiliser.
            merchant_reference (str | None): Référence marchande unique pour le suivi.
            custom_metadata (Dict[str, str] | None): Données personnalisées à stocker avec la transaction.
            description (str | None): Description de la transaction.

        Returns:
            Transaction: L'objet Transaction nouvellement créé (statut 'pending'), contenant `payment_url`.
        """
        return await self._transactions_service._create_transaction(
            setup=setup,
            client_infos=client_infos,
            montant_paiement=montant_paiement,
            api_key=api_key or self.default_api_key,
            callback_url=callback_url,
            merchant_reference=merchant_reference,
            custom_metadata=custom_metadata,
            description=description,
        )

    async def get_transaction_link(
        self, id_transaction: int, api_key: str | None = os.getenv("FEDAPAY_API_KEY")
    ) -> TransactionToken:
        """
        Récupère le jeton de paiement (`payment_token`) et l'URL de redirection
        pour initier le paiement d'une transaction existante.

        Args:
            id_transaction (int): L'ID de la transaction FedaPay.
            api_key (str | None): Clé API à utiliser.

        Returns:
            TransactionToken: Objet contenant le jeton (`payment_token`) et l'URL de paiement complète.
        """
        return await self._transactions_service._get_token_and_payment_link(
            id_transaction=id_transaction, api_key=api_key or self.default_api_key
        )

    async def set_payment_method(
        self,
        client_infos: UserData,
        setup: PaiementSetup,
        token: str,
        api_key: str | None = os.getenv("FEDAPAY_API_KEY"),
    ) -> TransactionPaymentMethodResponse:
        """
        Initie le processus de paiement en définissant la méthode (ex: Mobile Money) pour une transaction.

        Args:
            client_infos (UserData): Informations du client nécessaires pour la méthode (ex: numéro de téléphone).
            setup (PaiementSetup): Configuration de la méthode et du pays.
            token (str): Le jeton de paiement (`payment_token`) récupéré via `get_transaction_link`.
            api_key (str | None): Clé API à utiliser.

        Returns:
            TransactionPaymentMethodResponse: Réponse de l'API confirmant l'intention de paiement.
        """
        return await self._transactions_service._set_payment_method(
            client_infos=client_infos,
            setup=setup,
            token=token,
            api_key=api_key or self.default_api_key,
        )

    # ----------------------------------------
    # FAÇADE : Balances (Soldes)
    # ----------------------------------------

    async def get_all_balances(
        self, params: Optional[Dict[str, Any]] = None, api_key: Optional[str] = None
    ) -> BalanceListResponse:
        """
        Récupère la liste de tous les soldes (balances) associés aux différents modes de paiement du compte marchand.

        Args:
            params (Optional[Dict[str, Any]]): Paramètres de requête optionnels pour le filtrage ou la pagination.
            api_key (Optional[str]): Clé API à utiliser.

        Returns:
            BalanceListResponse: Une liste des objets Solde (Balance).
        """
        return await self._balances_service._get_all_balances(
            params=params, api_key=api_key or self.default_api_key
        )

    async def get_balance_by_id(
        self, balance_id: str, api_key: Optional[str] = None
    ) -> BalanceResponse:
        """
        Récupère les détails d'un solde spécifique par son ID.

        Args:
            balance_id (str): L'identifiant numérique unique du solde.
            api_key (Optional[str]): Clé API à utiliser.

        Returns:
            BalanceResponse: L'objet Solde (Balance) détaillé.
        """
        return await self._balances_service._get_balance_by_id(
            balance_id=balance_id, api_key=api_key or self.default_api_key
        )

    # ----------------------------------------
    # FAÇADE : Currencies (Devises)
    # ----------------------------------------

    async def get_all_currencies(
        self, params: Optional[Dict[str, Any]] = None, api_key: Optional[str] = None
    ) -> CurrencyListResponse:
        """
        Récupère la liste de toutes les devises supportées par FedaPay.

        Args:
            params (Optional[Dict[str, Any]]): Paramètres de requête optionnels (rarement utilisés pour les devises).
            api_key (Optional[str]): Clé API à utiliser.

        Returns:
            CurrencyListResponse: Une liste des objets Devise (Currency).
        """
        return await self._currencies_service._get_all_currencies(
            params=params, api_key=api_key or self.default_api_key
        )

    async def get_currency_by_id(
        self, currency_id: int, api_key: Optional[str] = None
    ) -> CurrencyResponse:
        """
        Récupère les détails d'une devise spécifique par son ID interne ou son code ISO (ex: 'XOF').

        Args:
            currency_id (str): L'ID ou le code ISO de la devise.
            api_key (Optional[str]): Clé API à utiliser.

        Returns:
            CurrencyResponse: L'objet Devise (Currency) détaillé.
        """
        return await self._currencies_service._get_currency_by_id(
            currency_id=currency_id, api_key=api_key or self.default_api_key
        )

    # ----------------------------------------
    # FAÇADE : Events (Événements)
    # ----------------------------------------

    async def get_all_events(
        self, params: Optional[Dict[str, Any]] = None, api_key: Optional[str] = None
    ) -> EventListResponse:
        """
        Récupère la liste paginée de tous les événements déclenchés par le compte marchand.

        Args:
            params (Optional[Dict[str, Any]]): Paramètres de requête pour le filtrage (ex: {'type': 'transaction.approved'}) et la pagination.
            api_key (Optional[str]): Clé API à utiliser.

        Returns:
            EventListResponse: Une liste des objets Événement (Event).
        """
        return await self._events_service._get_all_events(
            params=params, api_key=api_key or self.default_api_key
        )

    async def get_event_by_id(
        self, event_id: str, api_key: Optional[str] = None
    ) -> EventResponse:
        """
        Récupère les détails complets d'un événement spécifique par son ID.

        Args:
            event_id (str): L'identifiant unique de l'événement.
            api_key (Optional[str]): Clé API à utiliser.

        Returns:
            EventResponse: L'objet Événement (Event) détaillé.
        """
        return await self._events_service._get_event_by_id(
            event_id=event_id, api_key=api_key or self.default_api_key
        )

    # ----------------------------------------
    # FAÇADE : Logs (Journaux)
    # ----------------------------------------

    async def get_all_logs(
        self, params: Optional[Dict[str, Any]] = None, api_key: Optional[str] = None
    ) -> LogListResponse:
        """
        Récupère la liste des journaux d'activité (logs) de l'API, incluant les requêtes et les réponses.

        Args:
            params (Optional[Dict[str, Any]]): Paramètres de requête pour le filtrage (ex: {'status': 200}) et la pagination.
            api_key (Optional[str]): Clé API à utiliser.

        Returns:
            LogListResponse: Une liste des objets Journal (Log).
        """
        return await self._logs_service._get_all_logs(
            params=params, api_key=api_key or self.default_api_key
        )

    async def get_log_by_id(
        self, log_id: str, api_key: Optional[str] = None
    ) -> LogResponse:
        """
        Récupère les détails d'un journal d'activité spécifique par son ID.

        Args:
            log_id (str): L'identifiant unique du journal.
            api_key (Optional[str]): Clé API à utiliser.

        Returns:
            LogResponse: L'objet Journal (Log) détaillé.
        """
        return await self._logs_service._get_log_by_id(
            log_id=log_id, api_key=api_key or self.default_api_key
        )

    # ----------------------------------------
    # FAÇADE : Webhooks
    # ----------------------------------------

    async def get_all_webhooks(
        self, params: Optional[Dict[str, Any]] = None, api_key: Optional[str] = None
    ) -> WebhookListResponse:
        """
        Récupère la liste de tous les webhooks enregistrés sur le compte marchand.

        Args:
            params (Optional[Dict[str, Any]]): Paramètres de requête pour la pagination.
            api_key (Optional[str]): Clé API à utiliser.

        Returns:
            WebhookListResponse: Une liste des objets Webhook.
        """
        return await self._webhooks_service._get_all_webhooks(
            params=params, api_key=api_key or self.default_api_key
        )

    async def get_webhook_by_id(
        self, webhook_id: str, api_key: Optional[str] = None
    ) -> WebhookResponse:
        """
        Récupère les détails d'un webhook spécifique par son ID.

        Args:
            webhook_id (str): L'identifiant unique du webhook.
            api_key (Optional[str]): Clé API à utiliser.

        Returns:
            WebhookResponse: L'objet Webhook détaillé.
        """
        return await self._webhooks_service._get_webhook_by_id(
            webhook_id=webhook_id, api_key=api_key or self.default_api_key
        )
