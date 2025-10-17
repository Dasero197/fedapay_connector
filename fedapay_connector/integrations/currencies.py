from typing import Any, Dict, Optional

import aiohttp

from fedapay_connector import utils
from fedapay_connector.models import CurrencyListResponse, CurrencyResponse


class Currencies:
    """
    Client pour interagir avec les endpoints de gestion des Devises (Currencies)
    sur l'API FedaPay.
    """

    def __init__(self, api_url: str, logger):
        """
        Initialise le service Currencies.

        Args:
            api_url (str): L'URL de base de l'API FedaPay (ex: https://sandbox-api.fedapay.com/v1).
            logger: Instance de logger pour l'enregistrement des événements.
        """
        self.fedapay_api_url = api_url
        self._logger = logger

    async def _get_all_currencies(
        self, params: Optional[Dict[str, Any]] = None, api_key: Optional[str] = None
    ):
        """
        Récupère la liste de toutes les devises supportées par FedaPay ainsi que les modes
        de paiement associés à chacune.

        Args:
            params (Optional[Dict[str, Any]]): Paramètres de requête optionnels pour le filtrage ou la pagination.
            api_key (Optional[str]): Clé API du compte marchand pour l'authentification.

        Returns:
            CurrencyListResponse: Objet contenant la liste des devises et les métadonnées.
        """
        self._logger.info("Récupération de la liste complète des devises supportées.")
        header = utils.get_auth_header(api_key)

        async with aiohttp.ClientSession(
            headers=header, raise_for_status=True
        ) as session:
            async with session.get(
                f"{self.fedapay_api_url}/v1/currencies", params=params
            ) as response:
                response.raise_for_status()

                data = await response.json()
        return CurrencyListResponse(**data) if data else None

    async def _get_currency_by_id(
        self, currency_id: int, api_key: Optional[str] = None
    ):
        """
        Récupère les détails et modes de paiement supportés pour une devise spécifique
        en utilisant son identifiant ou son code ISO (e.g., 'XOF').

        Args:
            currency_id (str): L'identifiant interne de la devise ou son code ISO (e.g., '1' ou 'XOF').
            api_key (Optional[str]): Clé API du compte marchand pour l'authentification.

        Returns:
            CurrencyResponse: L'objet Devise détaillé.
        """
        self._logger.info(
            f"Récupération des détails de la devise ID/ISO : {currency_id}."
        )
        header = utils.get_auth_header(api_key)

        async with aiohttp.ClientSession(
            headers=header, raise_for_status=True
        ) as session:
            async with session.get(
                f"{self.fedapay_api_url}/v1/currencies/{currency_id}"
            ) as response:
                response.raise_for_status()

                data = await response.json()
        currency = data.get("v1/currency", None)
        return CurrencyResponse(**currency) if currency else None
