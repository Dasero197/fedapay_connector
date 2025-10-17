import os
from typing import Optional, Dict, Any

import aiohttp

from fedapay_connector import utils
from fedapay_connector.models import BalanceListResponse, BalanceResponse


class Balances:
    """
    Client pour interagir avec les endpoints de gestion des Soldes (Balances)
    sur l'API FedaPay.
    """

    def __init__(self, api_url: str, logger):
        """
        Initialise le service Balances.

        Args:
            api_url (str): L'URL de base de l'API FedaPay (ex: https://sandbox-api.fedapay.com/v1).
            logger: Instance de logger pour l'enregistrement des événements.
        """
        self.fedapay_api_url = api_url
        self._logger = logger

    async def _get_all_balances(
        self,
        params: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY"),
    ):
        """
        Récupère la liste de tous les soldes (balances) du compte marchand.

        Args:
            params (Optional[Dict[str, Any]]): Paramètres de requête pour la pagination
                et le filtrage (e.g., {'page': 2, 'per_page': 50}).
            api_key (Optional[str]): Clé API du compte marchand pour l'authentification.

        Returns:
            BalanceListResponse: Objet contenant la liste des soldes et les métadonnées de pagination.
        """
        self._logger.info(
            "Récupération de la liste des soldes (balances) avec les paramètres de requête."
        )
        header = utils.get_auth_header(api_key)

        async with aiohttp.ClientSession(
            headers=header, raise_for_status=True
        ) as session:
            async with session.get(
                f"{self.fedapay_api_url}/v1/balances", params=params
            ) as response:
                response.raise_for_status()

                data = await response.json()
        return BalanceListResponse(**data) if data else None

    async def _get_balance_by_id(
        self, balance_id: str, api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY")
    ):
        """
        Récupère les détails d'un solde spécifique par son ID unique.

        Args:
            balance_id (str): L'identifiant numérique du solde à récupérer.
            api_key (Optional[str]): Clé API du compte marchand pour l'authentification.

        Returns:
            BalanceResponse: L'objet Solde (Balance) détaillé.
        """
        self._logger.info(
            f"Récupération des détails du solde (balance) ID: {balance_id}."
        )
        header = utils.get_auth_header(api_key)

        async with aiohttp.ClientSession(
            headers=header, raise_for_status=True
        ) as session:
            async with session.get(
                f"{self.fedapay_api_url}/v1/balances/{balance_id}"
            ) as response:
                response.raise_for_status()

                data = await response.json()
        balance = data.get("v1/balance", None)
        return BalanceResponse(**balance) if balance else None
