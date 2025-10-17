"""
Script de test d'intégration réel pour la façade 'Integration' de Fedapay Connector.

CIBLE: API FedaPay Sandbox.

PRÉ-REQUIS ENVIRONNEMENTAUX:
- FEDAPAY_API_URL: L'URL de la sandbox (ex: https://sandbox-api.fedapay.com/v1).
- FEDAPAY_API_KEY: Clé API du compte marchand sandbox.
- TEST_CLIENT_PHONE: Numéro de téléphone pour les tests Mobile Money (ex: 22998765432).
- Les modèles Pydantic et la classe Integration doivent être importables.
"""

import asyncio
import os
import sys
import uuid
from typing import Optional
import aiohttp


try:
    from fedapay_connector.enums import MethodesPaiement, Pays
    from fedapay_connector import Integration
    from fedapay_connector.models import (
        PaiementSetup,
        Transaction,
        UserData,
        TypesPaiement,
        TransactionStatus,
        BalanceResponse,
        CurrencyResponse,
        EventResponse,
        LogResponse,
        WebhookResponse,
    )

    from fedapay_connector.exceptions import FedapayServerError
except ImportError as e:
    print(f"Erreur d'importation: {e}. Veuillez vérifier votre PYTHONPATH.")
    sys.exit(1)

# --- Configuration et Constantes ---
API_URL = os.getenv("FEDAPAY_API_URL")
API_KEY = os.getenv("FEDAPAY_API_KEY")
CLIENT_PHONE = "0164000001"
CALLBACK_URL = "https://example.com/fedapay/callback"
TEST_AMOUNT = 500

if not all([API_URL, API_KEY, CLIENT_PHONE]):
    print(
        "FATAL: Assurez-vous que FEDAPAY_API_URL, FEDAPAY_API_KEY et CLIENT_PHONE sont définis."
    )
    sys.exit(1)


class ConsoleLogger:
    def info(self, msg):
        print(f"✅ [INFO] {msg}")

    def error(self, msg):
        print(f"❌ [ERROR] {msg}")

    def warning(self, msg):
        print(f"⚠️ [WARNING] {msg}")

    def debug(self, msg):
        pass


TEST_LOGGER = ConsoleLogger()
INTEGRATION_CLIENT = Integration(
    api_url=API_URL, logger=TEST_LOGGER, default_api_key=API_KEY
)


async def safe_delete_transaction(fedapay_id: str):
    """Tente de supprimer la transaction pour nettoyer l'environnement."""
    if fedapay_id:
        TEST_LOGGER.info(
            f"Nettoyage: Tentative de suppression de la transaction ID: {fedapay_id}"
        )
        try:
            delete_status = await INTEGRATION_CLIENT.delete_transaction(fedapay_id)
            if delete_status.delete_status:
                TEST_LOGGER.info(
                    f"Nettoyage: Transaction {fedapay_id} supprimée avec succès."
                )
            else:
                TEST_LOGGER.warning(
                    f"Nettoyage: Échec de la suppression de {fedapay_id}. Code: {delete_status.status_code}"
                )
        except Exception as e:
            TEST_LOGGER.error(
                f"Nettoyage: Erreur critique lors de la suppression de {fedapay_id}: {e}"
            )


# ----------------------------------------------------------------------
# TESTS DES TRANSACTIONS (CRUD COMPLET)
# ----------------------------------------------------------------------


async def test_transactions_crud():
    """Teste toutes les méthodes de la façade Transactions."""
    TEST_LOGGER.info("=" * 50)
    TEST_LOGGER.info("DÉMARRAGE DU TEST: TRANSACTIONS (CRUD COMPLET)")
    TEST_LOGGER.info("=" * 50)

    transaction: Optional[Transaction] = None
    fedapay_id: Optional[str] = None
    merchant_ref = f"INT-TEST-{uuid.uuid4().hex[:10]}"

    try:
        # --- C: create_transaction ---
        setup = PaiementSetup(
            pays=Pays.benin,
            type_paiement=TypesPaiement.AVEC_REDIRECTION,  # Nécessite une redirection (le plus simple à tester)
            method=MethodesPaiement.moov,
        )
        client_infos = UserData(
            nom="Integration",
            prenom="Test",
            email="test.integration@example.com",
            tel=CLIENT_PHONE,
        )

        transaction = await INTEGRATION_CLIENT.create_transaction(
            setup=setup,
            client_infos=client_infos,
            montant_paiement=TEST_AMOUNT,
            callback_url=CALLBACK_URL,
            merchant_reference=merchant_ref,
            description="Test de création et suppression via la façade Integration.",
        )
        fedapay_id = str(transaction.id)
        assert transaction.status == TransactionStatus.pending, (
            "La transaction n'est pas 'pending' après création."
        )
        TEST_LOGGER.info(
            f"Transaction ID {fedapay_id} créée. Statut: {transaction.status}"
        )

        # --- U: update_transaction ---
        NEW_DESC = "Description mise à jour (TEST U)."
        updated_data = await INTEGRATION_CLIENT.update_transaction(
            fedapay_id=fedapay_id,
            data_to_update={
                "description": NEW_DESC,
            },
        )
        assert updated_data.description == NEW_DESC, (
            "La description n'a pas été mise à jour."
        )
        TEST_LOGGER.info("Transaction mise à jour avec succès.")

        # --- R: get_transaction_by_fedapay_id ---
        read_id = await INTEGRATION_CLIENT.get_transaction_by_fedapay_id(fedapay_id)
        assert read_id.id == int(fedapay_id), "Lecture par ID échouée."
        TEST_LOGGER.info("Transaction lue par ID avec succès.")

        # --- R: get_transaction_by_merchant_reference ---
        read_ref = await INTEGRATION_CLIENT.get_transaction_by_merchant_reference(
            merchant_ref
        )
        assert read_ref.id == int(fedapay_id), (
            "Lecture par référence marchande échouée."
        )
        TEST_LOGGER.info("Transaction lue par référence marchande avec succès.")

        # --- Utilité: get_transaction_link ---
        token_data = await INTEGRATION_CLIENT.get_transaction_link(int(fedapay_id))
        assert token_data.token, "Jeton (token) non récupéré."
        assert "http" in token_data.payment_link, "URL de paiement invalide."
        TEST_LOGGER.info("Lien de paiement et token récupérés.")

        # --- R: get_all_transactions ---
        list_response = await INTEGRATION_CLIENT.get_all_transactions(
            params={"per_page": 1}
        )
        assert len(list_response.transactions) > 0, "La liste de transactions est vide."
        TEST_LOGGER.info(
            f"Liste de transactions récupérée. Total: {list_response.meta.total_count}"
        )

    except aiohttp.ClientResponseError as e:
        TEST_LOGGER.error(
            f"Erreur API FedaPay (Transaction) : {e.status} - {e.message}"
        )
        raise
    except Exception as e:
        TEST_LOGGER.error(f"Erreur inattendue (Transaction) : {e}")
        raise
    finally:
        # --- D: delete_transaction ---
        await safe_delete_transaction(fedapay_id)
        TEST_LOGGER.info("=" * 50)
        TEST_LOGGER.info("TEST: TRANSACTIONS TERMINÉ")
        TEST_LOGGER.info("=" * 50)


# ----------------------------------------------------------------------
# TESTS DES AUTRES FAÇADES (LECTURE SEULE)
# ----------------------------------------------------------------------


async def test_read_facades():
    """Teste l'accessibilité des autres services (Balances, Currencies, Events, Logs, Webhooks)."""
    TEST_LOGGER.info("\n--- DÉMARRAGE DU TEST: AUTRES FAÇADES (READ) ---")

    # 1. Balances
    TEST_LOGGER.info("Test du service Balances...")
    balances_list = await INTEGRATION_CLIENT.get_all_balances()
    assert len(balances_list.balances) > 0, "Liste des balances vide."
    # Récupère l'ID du premier élément pour la lecture individuelle
    balance_id = balances_list.balances[0].id
    balance_details: BalanceResponse = await INTEGRATION_CLIENT.get_balance_by_id(
        str(balance_id)
    )
    assert balance_details.id == balance_id, "Lecture Balance par ID échouée."
    TEST_LOGGER.info("Service Balances: OK")

    # 2. Currencies
    TEST_LOGGER.info("Test du service Currencies...")
    currencies_list = await INTEGRATION_CLIENT.get_all_currencies()
    assert len(currencies_list.currencies) > 0, "Liste des devises vide."
    # Test avec un code ISO connu (plus fiable que l'ID interne)
    currency_details: CurrencyResponse = await INTEGRATION_CLIENT.get_currency_by_id(
        1
    )
    assert currency_details.iso == "XOF", "Lecture Currency par code ISO échouée."
    TEST_LOGGER.info("Service Currencies: OK")

    # 3. Events
    TEST_LOGGER.info("Test du service Events...")
    events_list = await INTEGRATION_CLIENT.get_all_events(params={"per_page": 1})
    if len(events_list.events) > 0:
        event_id = events_list.events[0].id
        event_details: EventResponse = await INTEGRATION_CLIENT.get_event_by_id(
            str(event_id)
        )
        assert event_details.id == event_id, "Lecture Event par ID échouée."
        TEST_LOGGER.info("Service Events: OK")
    else:
        TEST_LOGGER.warning("Service Events: Liste vide. Lecture par ID ignorée.")

    # 4. Logs
    TEST_LOGGER.info("Test du service Logs...")
    logs_list = await INTEGRATION_CLIENT.get_all_logs(params={"per_page": 1})
    if len(logs_list.logs) > 0:
        log_id = logs_list.logs[0].id
        log_details: LogResponse = await INTEGRATION_CLIENT.get_log_by_id(str(log_id))
        assert log_details.id == log_id, "Lecture Log par ID échouée."
        TEST_LOGGER.info("Service Logs: OK")
    else:
        TEST_LOGGER.warning("Service Logs: Liste vide. Lecture par ID ignorée.")

    # 5. Webhooks
    TEST_LOGGER.info("Test du service Webhooks...")
    webhooks_list = await INTEGRATION_CLIENT.get_all_webhooks()
    if len(webhooks_list.webhooks) > 0:
        webhook_id = webhooks_list.webhooks[0].id
        webhook_details: WebhookResponse = await INTEGRATION_CLIENT.get_webhook_by_id(
            str(webhook_id)
        )
        assert webhook_details.id == webhook_id, "Lecture Webhook par ID échouée."
        TEST_LOGGER.info("Service Webhooks: OK")
    else:
        TEST_LOGGER.warning("Service Webhooks: Liste vide. Lecture par ID ignorée.")

    TEST_LOGGER.info("\n--- FIN DU TEST: AUTRES FAÇADES (READ) ---")


# ----------------------------------------------------------------------
# EXÉCUTION
# ----------------------------------------------------------------------


async def main():
    try:
        # Exécuter les tests de transactions
        await test_transactions_crud()

        # Exécuter les tests de lecture pour les autres façades
        await test_read_facades()

        TEST_LOGGER.info(
            "\n🎉 *** TOUS LES TESTS D'INTÉGRATION TERMINÉS AVEC SUCCÈS *** 🎉"
        )

    except FedapayServerError as e:
        TEST_LOGGER.error(
            f"\n❌ *** ÉCHEC MAJEUR (Erreur API {e.status_code}) : {e.message} *** ❌"
        )
        sys.exit(1)
    except Exception as e:
        TEST_LOGGER.error(
            f"\n❌ *** ÉCHEC DES TESTS D'INTÉGRATION MAJEUR : {type(e).__name__} - {e} *** ❌"
        )
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
