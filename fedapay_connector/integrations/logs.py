from typing import Any, Dict, Optional

import aiohttp

from fedapay_connector import utils
from fedapay_connector.models import LogListResponse, LogResponse


class Logs:
    """
    Client pour interagir avec les endpoints de gestion des Journaux d'activité (Logs)
    sur l'API FedaPay. Les logs contiennent les requêtes API envoyées et les réponses reçues.
    """

    def __init__(self, api_url: str, logger):
        """
        Initialise le service Logs.

        Args:
            api_url (str): L'URL de base de l'API FedaPay (ex: https://sandbox-api.fedapay.com/v1).
            logger: Instance de logger pour l'enregistrement des événements.
        """
        self.fedapay_api_url = api_url
        self._logger = logger

    async def _get_all_logs(
        self, params: Optional[Dict[str, Any]] = None, api_key: Optional[str] = None
    ):
        """
        Récupère la liste des journaux d'activité (logs) de l'API pour le compte marchand.

        Args:
            params (Optional[Dict[str, Any]]): Paramètres de requête pour la pagination
                et le filtrage (e.g., 'method', 'status', 'page', 'url').
            api_key (Optional[str]): Clé API du compte marchand pour l'authentification.

        Returns:
            LogListResponse: Objet contenant la liste des journaux et les métadonnées de pagination.
        """
        self._logger.info(
            "Récupération de la liste des journaux (Logs) avec filtres optionnels."
        )
        header = utils.get_auth_header(api_key)

        async with aiohttp.ClientSession(
            headers=header, raise_for_status=True
        ) as session:
            async with session.get(
                f"{self.fedapay_api_url}/v1/logs", params=params
            ) as response:
                response.raise_for_status()

                data = await response.json()
        return LogListResponse(**data) if data else None

    async def _get_log_by_id(self, log_id: str, api_key: Optional[str] = None):
        """
        Récupère les détails complets d'un journal d'activité spécifique par son ID,
        incluant le corps de la requête et de la réponse.

        Args:
            log_id (str): L'identifiant unique du journal d'activité.
            api_key (Optional[str]): Clé API du compte marchand pour l'authentification.

        Returns:
            LogResponse: L'objet Journal (Log) détaillé.
        """
        self._logger.info(f"Récupération des détails du journal (Log) ID : {log_id}.")
        header = utils.get_auth_header(api_key)

        async with aiohttp.ClientSession(
            headers=header, raise_for_status=True
        ) as session:
            async with session.get(
                f"{self.fedapay_api_url}/v1/logs/{log_id}"
            ) as response:
                response.raise_for_status()

                data = await response.json()
        log = data.get("v1/log", None)
        return LogResponse(**log) if log else None
