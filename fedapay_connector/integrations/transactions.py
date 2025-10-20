import logging
import os
from typing import Any, Dict, Optional
import aiohttp
from fedapay_connector import utils
from fedapay_connector.models import (
    PaiementSetup,
    TransactionDeleteStatus,
    TransactionListResponse,
    TransactionPaymentMethodResponse,
    TransactionToken,
    UserData,
    Transaction,
)
from fedapay_connector.utils import get_currency


class Transactions:
    def __init__(self, api_url: str, logger: logging.Logger):
        self.fedapay_api_url = api_url
        self._logger = logger

    async def _create_transaction(
        self,
        setup: PaiementSetup,
        client_infos: Optional[UserData],
        montant_paiement: int,
        callback_url: Optional[str] = None,
        api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY"),
        merchant_reference: Optional[str] = None,
        custom_metadata: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ):
        """
        Crée une nouvelle transaction sur l'API FedaPay et retourne son état initial.

        Args:
            setup (PaiementSetup): Configuration du mode de paiement et du pays.
            client_infos (Optional[UserData]): Informations détaillées du client (nom, email, téléphone).
            montant_paiement (int): Montant total à payer, en unités de la devise (ex: centimes ou francs).
            callback_url (Optional[str]): URL de rappel pour les notifications asynchrones de FedaPay.
            api_key (Optional[str]): Clé API du compte marchand pour l'authentification.
            merchant_reference (Optional[str]): Référence unique fournie par le marchand pour le suivi.
            custom_metadata (Optional[Dict[str, str]]): Données personnalisées à associer à la transaction.
            description (Optional[str]): Description optionelle de la transaction.

        Returns:
            Transaction: Instance du modèle Transaction
        """
        self._logger.info("Initialisation de la transaction avec FedaPay.")
        header = utils.get_auth_header(api_key=api_key)

        body = {
            "description": f"Transaction pour {client_infos.prenom} {client_infos.nom}"
            if description is None
            else description,
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
            }
            if client_infos is not None
            else None,
            "custom_metadata": custom_metadata,
            "merchant_reference": merchant_reference,
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

        return Transaction(**init_response)

    async def _get_token_and_payment_link(
        self, id_transaction: int, api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY")
    ):
        """
        Génère et récupère le jeton de paiement (payment_token) et l'URL de redirection
        pour une transaction existante.

        Args:
            id_transaction (int): L'ID de la transaction FedaPay.
            api_key (Optional[str]): Clé API pour l'authentification.

        Returns:
            TransactionToken: Objet contenant le jeton et le lien de paiement.

        Example:
            token_data = await paiement_fedapay_class._get_token_and_payment_link(12345)
        """
        self._logger.info(
            f"Récupération du token pour la transaction ID: {id_transaction}"
        )
        header = utils.get_auth_header(api_key=api_key)

        async with aiohttp.ClientSession(
            headers=header, raise_for_status=True
        ) as session:
            async with session.post(
                f"{self.fedapay_api_url}/v1/transactions/{id_transaction}/token"
            ) as response:
                response.raise_for_status()
                data = await response.json()

        self._logger.info(f"Token récupéré avec succès: {data}")

        return TransactionToken(**data)

    async def _set_payment_method(
        self,
        client_infos: UserData,
        setup: PaiementSetup,
        token: str,
        api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY"),
    ):
        """
        Définit et initie le paiement pour une transaction via une méthode spécifique
        (e.g., Mobile Money) en utilisant le jeton de paiement.

        Args:
            client_infos (UserData): Informations du client.
            setup (PaiementSetup): Configuration du paiement, incluant la méthode et le pays.
            token (str): Jeton de paiement (payment_token) de la transaction.
            api_key (Optional[str]): Clé API pour l'authentification.

        Returns:
            TransactionPaymentMethodResponse: Réponse de l'API confirmant l'intention de paiement.

        Example:
            methode_data = await paiement_fedapay_class._set_payment_method(client_infos, setup, "token123")
        """
        self._logger.info(
            f"Définition de la méthode de paiement pour le token: {token}"
        )
        header = utils.get_auth_header(api_key=api_key)

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

        return TransactionPaymentMethodResponse(**data)

    async def _get_transaction_by_fedapay_id(
        self, fedapay_id: str, api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY")
    ):
        """
        Récupère les détails complets d'une transaction unique en utilisant son ID FedaPay.

        Args:
            fedapay_id (str): L'identifiant unique numérique de la transaction.

        Returns:
            Transaction: L'objet Transaction complet correspondant à l'ID.
        """
        self._logger.info(f"Récupération de la transaction FedaPay ID: {fedapay_id}")
        header = utils.get_auth_header(api_key)

        async with aiohttp.ClientSession(
            headers=header, raise_for_status=True
        ) as session:
            async with session.get(
                f"{self.fedapay_api_url}/v1/transactions/{fedapay_id}"
            ) as response:
                response.raise_for_status()

                data = await response.json()
        return Transaction(**data.get("v1/transaction"))

    async def _get_transaction_by_merchant_reference(
        self,
        merchant_reference: str,
        api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY"),
    ):
        """
        Récupère une transaction unique en utilisant sa référence marchande (`merchant_reference`).

        Note: Cet appel utilise un endpoint spécifique pour les références marchandes ou une recherche
        générique. (Vérifiez l'URL de l'API pour cet endpoint).

        Args:
            merchant_reference (str): La référence marchande (`merchant_reference`) fournie lors de la création.

        Returns:
            Transaction: L'objet Transaction correspondant, ou lève une exception si non trouvé.
        """
        self._logger.info(
            f"Recherche de transaction par merchant_reference: {merchant_reference}"
        )
        header = utils.get_auth_header(api_key)

        # La recherche par défaut utilise l'endpoint de recherche avec un paramètre 'q'

        async with aiohttp.ClientSession(
            headers=header, raise_for_status=True
        ) as session:
            async with session.get(
                f"{self.fedapay_api_url}/v1/transactions/merchant/{merchant_reference}"
            ) as response:
                response.raise_for_status()
                data = await response.json()
        return Transaction(**data.get("v1/transaction"))

    async def _delete_transaction(
        self, fedapay_id: str, api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY")
    ) -> TransactionDeleteStatus:
        """
        Annule et supprime définitivement une transaction par son ID, si son statut le permet.
        Cette opération n'est généralement possible que si le paiement n'est pas encore initié.

        Args:
            fedapay_id (str): L'identifiant unique de la transaction à annuler.

        Returns:
            TransactionDeleteStatus: Objet indiquant le statut de la tentative de suppression (succès ou échec).
        """
        self._logger.warning(
            f"Tentative de suppression de la transaction FedaPay ID: {fedapay_id}"
        )
        header = utils.get_auth_header(api_key)

        async with aiohttp.ClientSession(
            headers=header,
            raise_for_status=True,
        ) as session:
            async with session.delete(
                f"{self.fedapay_api_url}/v1/transactions/{fedapay_id}"
            ) as response:
                if response.status in [200, 204]:
                    self._logger.info(
                        f"Transaction {fedapay_id} supprimée/annulée avec succès."
                    )
                    return TransactionDeleteStatus(
                        delete_status=True, status_code=response.status
                    )
                response.raise_for_status()

    async def _update_transaction(
        self,
        fedapay_id: str,
        data_to_update: Dict[str, Any],
        api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY"),
    ):
        """
        Met à jour des champs modifiables d'une transaction existante
        (ex: description, `custom_metadata`).

        Args:
            fedapay_id (str): L'identifiant unique de la transaction.
            data_to_update (Dict[str, Any]): Les clés et valeurs à modifier, encapsulées dans un dictionnaire.

        Returns:
            Transaction: L'objet Transaction mis à jour.
        """
        self._logger.info(f"Mise à jour de la transaction FedaPay ID: {fedapay_id}")
        header = utils.get_auth_header(api_key)

        async with aiohttp.ClientSession(
            headers=header, raise_for_status=True
        ) as session:
            async with session.put(
                f"{self.fedapay_api_url}/v1/transactions/{fedapay_id}", json=data_to_update
            ) as response:
                response.raise_for_status()
                data = await response.json()
        transaction = data.get("v1/transaction", None)
        return Transaction(**transaction)

    async def _get_all_transactions(
        self,
        params: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY"),
    ):
        """
        Récupère une liste paginée de toutes les transactions du compte marchand.

        Args:
            params (Optional[Dict[str, Any]]): Paramètres de requête pour le filtrage et la pagination

        Returns:
            TransactionListResponse: Objet contenant la liste des transactions (`v1/transactions`) et les métadonnées de pagination.
        """
        self._logger.info("Récupération de toutes les transactions.")
        header = utils.get_auth_header(api_key)

        async with aiohttp.ClientSession(
            headers=header, raise_for_status=True
        ) as session:
            async with session.get(
                f"{self.fedapay_api_url}/v1/transactions/search", params=params
            ) as response:
                response.raise_for_status()
                data = await response.json()
        return TransactionListResponse(**data) if data else None
