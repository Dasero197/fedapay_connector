"""
Script de test d'intégration complet pour la classe FedapayConnector.

CIBLE: L'API FedaPay Sandbox.

PRÉ-REQUIS ENVIRONNEMENTAUX:
- FEDAPAY_API_URL: URL de la sandbox.
- FEDAPAY_API_KEY: Clé API du compte marchand sandbox.
- FEDAPAY_AUTH_KEY: Clé secrète de vérification des webhooks FedaPay (pour le serveur local).
- TEST_CLIENT_PHONE: Numéro de téléphone pour les tests.
- Assurez-vous que le répertoire 'fedapay_connector_persisted_data' est vide ou inexistant avant le premier run
  si vous voulez tester le cas 'load_persisted_listening_processes' sans données.
"""

import asyncio
import os
import sys
import uuid
from typing import List, Optional, Dict, Any

try:
    from fedapay_connector import (
        Pays,
        MethodesPaiement,
        TypesPaiement,
        FedapayConnector,
        PaiementSetup,
        UserData,
        EventFutureStatus,
        PaymentHistory,
        WebhookHistory,
        FedapayPay,
        TransactionStatus,
        TransactionIsNotPendingAnymore,
    )
except ImportError as e:
    print(f"❌ Erreur d'importation: {e}. Vérifiez votre PYTHONPATH.")
    sys.exit(1)

LISTEN_PORT = 8000
LISTEN_ENDPOINT = "utils/webhooks"

API_KEY = os.getenv("FEDAPAY_API_KEY")
FEDAPAY_WEBHOOKS_SECRET_KEY = os.getenv("FEDAPAY_AUTH_KEY")
TEST_CLIENT = UserData(
    nom="ASSOGBA",
    prenom="Dayane",
    email="test.dayane.connector@example.com",
    tel="0164000001",
)
TEST_AMOUNT = 350
TIMEOUT_FINALISE = 5  # Timeout court pour forcer le cas TIMEOUT

if not all([os.getenv("FEDAPAY_API_URL"), API_KEY, FEDAPAY_WEBHOOKS_SECRET_KEY]):
    print(
        "FATAL: Les variables FEDAPAY_API_URL, FEDAPAY_API_KEY, et FEDAPAY_AUTH_KEY (webhook secret) doivent être définies."
    )
    sys.exit(1)

# Variables globales pour suivre l'exécution des callbacks et des tests
CALLBACK_STATUS: Dict[str, Any] = {
    "payment_count": 0,
    "webhook_count": 0,
    "reload_status": None,
    "finalise_results": [],
}


# Logger minimal pour la console
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
GLOBAL_CONNECTOR: Optional[FedapayConnector] = None

# ----------------------------------------------------------------------
# FONCTIONS DE CALLBACK POUR LE TEST
# ----------------------------------------------------------------------


async def reload_finished_callback(
    future_event_status: EventFutureStatus, data: Optional[List[WebhookHistory]]
):
    """Callback pour `load_persisted_listening_processes`."""
    global CALLBACK_STATUS
    CALLBACK_STATUS["reload_status"] = future_event_status
    CALLBACK_STATUS["reload_data"] = data
    TEST_LOGGER.info(
        f"Callback (Reload Finished) appelé. Statut: {future_event_status.name}"
    )


async def payment_callback(payment: PaymentHistory):
    """Callback pour `set_payment_callback_function`."""
    global CALLBACK_STATUS
    CALLBACK_STATUS["payment_count"] += 1
    TEST_LOGGER.info(f"Callback (Payment) appelé. ID: {payment.transaction_data.id}")


async def webhook_callback(webhook_data: WebhookHistory):
    """Callback pour `set_webhook_callback_function`."""
    global CALLBACK_STATUS
    CALLBACK_STATUS["webhook_count"] += 1
    TEST_LOGGER.info(f"Callback (Webhook) appelé. Type: {webhook_data.name}")


# ----------------------------------------------------------------------
# TESTS DE DÉMARRAGE ET CONFIGURATION
# ----------------------------------------------------------------------


async def test_01_singleton_and_config() -> FedapayConnector:
    """Test des méthodes FedapayConnector.__new__ et __init__."""
    print("\n" + "=" * 50)
    print("PHASE 1: SINGLETON, CONFIGURATION & CALLBACKS")
    print("=" * 50)

    # 1. Test Singleton et passage des arguments
    instance1 = FedapayConnector(
        use_listen_server=True,
        listen_server_port=LISTEN_PORT,
        listen_server_endpoint_name=LISTEN_ENDPOINT,
        fedapay_webhooks_secret_key=FEDAPAY_WEBHOOKS_SECRET_KEY,
        db_url="sqlite:///test_singleton/processes.db",
    )
    instance2 = FedapayConnector(use_listen_server=False, listen_server_port=9000)

    assert instance1 is instance2, (
        "❌ Échec Singleton: Les instances ne sont pas les mêmes."
    )
    # Vérifie que les paramètres de la première instance ont été conservés
    assert instance2.use_internal_listener is True, (
        "❌ Config: use_internal_listener perdu."
    )
    assert instance2.listen_server_port == LISTEN_PORT, "❌ Config: Port perdu."
    print("✅ FedapayConnector se comporte comme un Singleton.")

    # 2. Test Enregistrement des Callbacks
    instance1.set_payment_callback_function(payment_callback)
    instance1.set_webhook_callback_function(webhook_callback)
    instance1.set_on_persited_listening_processes_loading_finished_callback(
        reload_finished_callback
    )

    assert instance1._payment_callback is payment_callback, (
        "❌ Callback: Échec set_payment_callback_function."
    )
    assert instance1._webhooks_callback is webhook_callback, (
        "❌ Callback: Échec set_webhook_callback_function."
    )
    print("✅ Callbacks enregistrés avec succès.")

    # 3. Test Démarrage du serveur et chargement des processus
    instance1.start_webhook_server()
    print(f"✅ Serveur Webhook démarré sur le port {instance1.listen_server_port}.")

    await instance1.load_persisted_listening_processes()
    return instance1


# ----------------------------------------------------------------------
# TESTS DE L'API FÉDAPAY (FEDAPAY_PAY, FINALIZE, UTILS)
# ----------------------------------------------------------------------


async def test_02_transaction_lifecycle(fedapay: FedapayConnector):
    """Test de fedapay_pay, fedapay_finalise (TIMEOUT) et fedapay_save_webhook_data."""
    print("\n" + "=" * 50)
    print("PHASE 2: TRANSACTIONS & ÉVÉNEMENTS")
    print("=" * 50)

    merchant_ref = f"REF-{uuid.uuid4().hex[:8]}"

    # --- 1. Test fedapay_pay (avec et sans redirection) ---
    setup_redirect = PaiementSetup(
        pays=Pays.benin, type_paiement=TypesPaiement.AVEC_REDIRECTION
    )
    setup_no_redirect = PaiementSetup(
        pays=Pays.benin,
        method=MethodesPaiement.moov,
        type_paiement=TypesPaiement.SANS_REDIRECTION,
    )

    # Paiement 1 : Avec redirection (le plus simple pour la Sandbox)
    resp1: FedapayPay = await fedapay.fedapay_pay(
        setup=setup_redirect,
        client_infos=TEST_CLIENT,
        montant_paiement=TEST_AMOUNT,
        merchant_reference=merchant_ref,
        description="Test avec redirection",
    )
    assert resp1.transaction_data.id > 0, "❌ Pay: Échec création T1 (pas d'ID)."
    assert resp1.link_and_token_data.payment_link, "❌ Pay: Échec lien de paiement."
    assert resp1.status == TransactionStatus.pending, (
        "❌ Pay: Statut T1 n'est pas 'pending'."
    )
    print(
        f"✅ Transaction T1 (ID {resp1.transaction_data.id}) créée (AVEC redirection)."
    )

    # Paiement 2 : Sans redirection (teste l'appel à _set_payment_method)
    resp2: FedapayPay = await fedapay.fedapay_pay(
        setup=setup_no_redirect,
        client_infos=TEST_CLIENT,
        montant_paiement=TEST_AMOUNT + 100,
        merchant_reference=f"REF-{uuid.uuid4().hex[:8]}",
        description="Test sans redirection",
    )
    assert resp2.transaction_data.id > 0, "❌ Pay: Échec création T2 (pas d'ID)."
    assert resp2.set_methode_data, (
        "❌ Pay: Échec: set_methode_data est vide (sans redirection)."
    )
    print(
        f"✅ Transaction T2 (ID {resp2.transaction_data.id}) créée (SANS redirection)."
    )

    # 3. Vérification des Callbacks de Paiement
    await asyncio.sleep(0.5)  # Laisser le temps aux tâches de callback de se lancer
    assert CALLBACK_STATUS["payment_count"] == 2, (
        "❌ Callback: payment_callback n'a pas été appelé 2 fois."
    )
    print(
        "✅ Les callbacks de paiement se sont déclenchés correctement (en tâche séparée)."
    )

    # --- 2. Test fedapay_finalise (Cas TIMEOUT) ---
    # Nous forçons un timeout, ce qui teste _await_external_event et _run_on_transaction_timeout_callback

    future_event_status, data = await fedapay.fedapay_finalise(
        id_transaction=resp1.transaction_data.id, timeout=TIMEOUT_FINALISE
    )

    assert future_event_status == EventFutureStatus.TIMEOUT, (
        "❌ Finalise: N'a pas renvoyé TIMEOUT après le délai."
    )
    assert data is None, (
        "❌ Finalise: Des données ont été retournées malgré le TIMEOUT."
    )
    print(
        f"✅ fedapay_finalise a correctement expiré après {TIMEOUT_FINALISE}s (démontre le fonctionnement interne du timeout)."
    )

    # --- 3. Test fedapay_save_webhook_data (avec simulation) ---
    TEST_WEBHOOK_ID = resp2.transaction_data.id  # Utilise T2, dont l'écoute est terminée mais la transaction est toujours 'pending'

    simulated_webhook = {
        "id": "evt_" + uuid.uuid4().hex,
        "name": "transaction.approved",
        "entity": resp2.transaction_data.model_dump(),
    }

    # Sauvegarde du webhook
    await fedapay.fedapay_save_webhook_data(simulated_webhook)

    await asyncio.sleep(0.5)  # Laisser le temps au callback de s'exécuter
    assert CALLBACK_STATUS["webhook_count"] >= 1, (
        "❌ Webhook: webhook_callback n'a pas été appelé."
    )
    print("✅ fedapay_save_webhook_data a fonctionné et déclenché le webhook_callback.")

    # Retourne T2 pour l'étape suivante (Cancel)
    return resp2


# ----------------------------------------------------------------------
# TESTS DE LECTURE ET ANNULATION (CRUD DÉTAILLÉ)
# ----------------------------------------------------------------------


async def test_03_utils_and_cancellation(
    fedapay: FedapayConnector, transaction_to_cancel: FedapayPay
):
    """Test des méthodes de lecture et d'annulation."""
    print("\n" + "=" * 50)
    print("PHASE 3: UTILITAIRES & ANNULATION")
    print("=" * 50)

    # --- 1. Test fedapay_get_transaction_data ---
    ID = transaction_to_cancel.transaction_data.id

    data_by_id = await fedapay.fedapay_get_transaction_data(ID)
    assert data_by_id.id == ID, "❌ Get: fedapay_get_transaction_data (par ID) échoué."
    print("✅ fedapay_get_transaction_data (par ID) fonctionne.")

    # --- 2. Test fedapay_get_transaction_data_by_merchant_id ---
    MERCHANT_REF = transaction_to_cancel.transaction_data.merchant_reference

    data_by_ref = await fedapay.fedapay_get_transaction_data_by_merchant_id(
        MERCHANT_REF
    )
    assert data_by_ref.id == ID, (
        "❌ Get: fedapay_get_transaction_data_by_merchant_id (par référence) échoué."
    )
    print("✅ fedapay_get_transaction_data_by_merchant_id fonctionne.")

    # --- 3. Test fedapay_cancel_transaction ---
    # Tente d'annuler T2,
    try:
        not_pending_anymore = False
        cancel_status = await fedapay.fedapay_cancel_transaction(ID)
    except TransactionIsNotPendingAnymore:
        print(
            "✅ Cancel: fedapay_cancel_transaction a levé TransactionIsNotPendingAnymore ce qui veut dire que la transaction n'est plus pending."
        )
        not_pending_anymore = True

    # Dans la Sandbox, la suppression réussit généralement si 'pending'.
    assert not_pending_anymore is True or cancel_status.delete_status is True, (
        "❌ Cancel: fedapay_cancel_transaction a échoué (delete_status est False et staus code n'est pas 403)."
    )
    print(f"✅ fedapay_cancel_transaction a réussi sur T2 (ID {ID}).")

    # --- 4. Test fedapay_cancel_transaction sur une transaction résolue (pour tester l'exception) ---
    try:
        # Tente d'annuler T2 une seconde fois, elle est maintenant 'canceled' sur l'API
        await fedapay.fedapay_cancel_transaction(ID)
        print(
            "⚠️ Cancel: fedapay_cancel_transaction n'a pas levé d'exception lors de la tentative de double-annulation."
        )
    except TransactionIsNotPendingAnymore:
        print(
            "✅ Cancel: fedapay_cancel_transaction a levé TransactionIsNotPendingAnymore comme attendu."
        )
    except Exception as e:
        print(
            f"❌ Cancel: fedapay_cancel_transaction a levé une exception inattendue: {type(e).__name__}."
        )


# ----------------------------------------------------------------------
# TESTS DE GESTION DES FUTURES ET NETTOYAGE
# ----------------------------------------------------------------------


async def test_04_futures_and_cleanup(fedapay: FedapayConnector):
    """Test de cancel_all_future_event et shutdown_cleanup."""
    print("\n" + "=" * 50)
    print("PHASE 4: GESTION DES FUTURES & NETTOYAGE")
    print("=" * 50)

    # 1. Création d'une Future en attente (sans finalise)
    FUTURE_ID = 9999999  # Utilise un ID bidon pour une écoute locale

    # Crée et démarre l'écoute sans faire le "finalise" bloquant
    future = await fedapay._event_manager.create_future(
        id_transaction=FUTURE_ID, timeout=120
    )
    assert future.done() is False, "❌ Futures: La future de test est déjà terminée."

    # 2. Test cancel_future_event
    await fedapay.cancel_future_event(FUTURE_ID)
    await asyncio.sleep(
        1
    )  # cancel future ne l'annule pas instantanement mais programme plutot l'annulation
    assert future.done() is True, (
        "❌ Futures: cancel_future_event n'a pas terminé la future."
    )
    print(f"✅ cancel_future_event a réussi sur l'ID {FUTURE_ID}.")

    # 3. Test cancel_all_future_event (Crée une nouvelle future à annuler)
    FUTURE_ID_2 = 9999998
    future2 = await fedapay._event_manager.create_future(
        id_transaction=FUTURE_ID_2, timeout=120
    )
    await fedapay.cancel_all_future_event(reason="Fin de test")
    await asyncio.sleep(
        1
    )  # cancel future ne l'annule pas instantanement mais programme plutot l'annulation

    # Le statut doit être annulé ou un état final
    assert future2.done() is True, (
        "❌ Futures: cancel_all_future_event n'a pas terminé la future."
    )
    print("✅ cancel_all_future_event a réussi.")

    # 4. Test shutdown_cleanup
    # Simule une tâche de callback en cours (voir code initial)
    async def long_running_callback():
        await asyncio.sleep(
            2
        )  # Devrait être gérée par le cleanup (timeout par défaut de 10s)

    long_task = asyncio.create_task(long_running_callback())
    fedapay._callback_tasks.add(long_task)

    await fedapay.shutdown_cleanup()
    assert long_task.done(), (
        "❌ Cleanup: La tâche de callback n'a pas été terminée par shutdown_cleanup."
    )
    print("✅ shutdown_cleanup exécuté avec succès (serveur arrêté, tâches terminées).")


# ----------------------------------------------------------------------
# EXÉCUTION
# ----------------------------------------------------------------------


async def main():
    global GLOBAL_CONNECTOR
    try:
        GLOBAL_CONNECTOR = await test_01_singleton_and_config()

        transaction_to_cancel = await test_02_transaction_lifecycle(GLOBAL_CONNECTOR)

        await test_03_utils_and_cancellation(GLOBAL_CONNECTOR, transaction_to_cancel)

        await test_04_futures_and_cleanup(GLOBAL_CONNECTOR)

        print("\n🎉 *** TOUS LES TESTS DE FedapayConnector TERMINÉS AVEC SUCCÈS *** 🎉")

    except Exception as e:
        TEST_LOGGER.error(
            f"\n❌ *** ÉCHEC GLOBAL DU TEST: {type(e).__name__} - {e} *** ❌"
        )
        # Tentative de nettoyage si l'instance existe
        if GLOBAL_CONNECTOR:
            await GLOBAL_CONNECTOR.shutdown_cleanup()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
