from typing import Any, Dict, Optional

import aiohttp

from fedapay_connector import utils
from fedapay_connector.models import EventListResponse, EventResponse


class Events:
    """
    Client pour interagir avec les endpoints de gestion des Événements (Events)
    sur l'API FedaPay. Les événements sont des enregistrements des changements
    d'état des ressources (e.g., transaction.approved, payment_method.created).
    """

    def __init__(self, api_url: str, logger):
        """
        Initialise le service Events.

        Args:
            api_url (str): L'URL de base de l'API FedaPay (ex: https://sandbox-api.fedapay.com/v1).
            logger: Instance de logger pour l'enregistrement des événements.
        """
        self.fedapay_api_url = api_url
        self._logger = logger

    async def _get_all_events(
        self, params: Optional[Dict[str, Any]] = None, api_key: Optional[str] = None
    ):
        """
        Récupère la liste de tous les événements déclenchés par le compte marchand.

        Args:
            params (Optional[Dict[str, Any]]): Paramètres de requête pour la pagination
                et le filtrage (e.g., 'type', 'created_at', 'page').
            api_key (Optional[str]): Clé API du compte marchand pour l'authentification.

        Returns:
            EventListResponse: Objet contenant la liste des événements et les métadonnées de pagination.
        """
        self._logger.info(
            "Récupération de la liste des événements (Events) avec filtres optionnels."
        )
        header = utils.get_auth_header(api_key)

        async with aiohttp.ClientSession(
            headers=header, raise_for_status=True
        ) as session:
            async with session.get(
                f"{self.fedapay_api_url}/v1/events", params=params
            ) as response:
                response.raise_for_status()

                data = await response.json()
        return EventListResponse(**data) if data else None

    async def _get_event_by_id(self, event_id: str, api_key: Optional[str] = None):
        """
        Récupère les détails complets d'un événement spécifique, incluant les données
        de la ressource concernée (payload).

        Args:
            event_id (str): L'identifiant unique de l'événement FedaPay.
            api_key (Optional[str]): Clé API du compte marchand pour l'authentification.

        Returns:
            EventResponse: L'objet Événement (Event) détaillé.
        """
        self._logger.info(f"Récupération des détails de l'événement ID : {event_id}.")
        header = utils.get_auth_header(api_key)

        async with aiohttp.ClientSession(
            headers=header, raise_for_status=True
        ) as session:
            async with session.get(
                f"{self.fedapay_api_url}/v1/events/{event_id}"
            ) as response:
                response.raise_for_status()

                data = await response.json()
        event = data.get("v1/event", None)
        return EventResponse(**event) if event else None
