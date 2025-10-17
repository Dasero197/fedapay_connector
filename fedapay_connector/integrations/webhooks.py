from typing import Any, Dict, Optional

import aiohttp

from fedapay_connector import utils
from fedapay_connector.models import WebhookListResponse, WebhookResponse


class Webhooks:  # Correction du nom de la classe
    """
    Client pour interagir avec les endpoints de gestion des Webhooks
    sur l'API FedaPay. Les webhooks sont utilisés pour la notification
    asynchrone des événements.
    """

    def __init__(self, api_url: str, logger):
        """
        Initialise le service Webhooks.

        Args:
            api_url (str): L'URL de base de l'API FedaPay (ex: https://sandbox-api.fedapay.com/v1).
            logger: Instance de logger pour l'enregistrement des événements.
        """
        self.fedapay_api_url = api_url
        self._logger = logger

    async def _get_all_webhooks(
        self, params: Optional[Dict[str, Any]] = None, api_key: Optional[str] = None
    ):
        """
        Récupère la liste de tous les webhooks enregistrés sur le compte marchand.

        Args:
            params (Optional[Dict[str, Any]]): Paramètres de requête pour la pagination.
            api_key (Optional[str]): Clé API du compte marchand pour l'authentification.

        Returns:
            WebhookListResponse: Objet contenant la liste des webhooks et les métadonnées de pagination.
        """
        self._logger.info(
            "Récupération de la liste des webhooks avec filtres optionnels."
        )
        header = utils.get_auth_header(api_key)

        async with aiohttp.ClientSession(
            headers=header, raise_for_status=True
        ) as session:
            async with session.get(
                f"{self.fedapay_api_url}/v1/webhooks", params=params
            ) as response:
                response.raise_for_status()

                data = await response.json()
        return WebhookListResponse(**data) if data else None

    async def _get_webhook_by_id(self, webhook_id: str, api_key: Optional[str] = None):
        """
        Récupère les détails d'un webhook spécifique par son ID.

        Args:
            webhook_id (str): L'identifiant unique du webhook.
            api_key (Optional[str]): Clé API du compte marchand pour l'authentification.

        Returns:
            WebhookResponse: L'objet Webhook détaillé.
        """
        self._logger.info(f"Récupération des détails du webhook ID : {webhook_id}.")
        header = utils.get_auth_header(api_key)

        async with aiohttp.ClientSession(
            headers=header, raise_for_status=True
        ) as session:
            async with session.get(
                f"{self.fedapay_api_url}/v1/webhooks/{webhook_id}"
            ) as response:
                response.raise_for_status()

                data = await response.json()

        # Correction de l'erreur: Utiliser "v1/webhook" au lieu de "v1/currency"
        webhook = data.get("v1/webhook", None)
        return WebhookResponse(**webhook) if webhook else None
