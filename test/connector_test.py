from fedapay_connector import (
    Pays,
    FedapayPay,
    MethodesPaiement,
    TypesPaiement,
    FedapayConnector,
    PaiementSetup,
    UserData,
    EventFutureStatus,
    PaymentHistory,
    WebhookHistory,
)
import asyncio


async def main():
    async def run_after_finalise(
        future_event_status: EventFutureStatus, data: list[WebhookHistory] | None
    ):
        if future_event_status == EventFutureStatus.TIMEOUT:
            # Vérification manuelle du statut de la transaction
            print("\nLa transaction a expiré. Vérification manuelle du statut...\n")

        elif future_event_status == EventFutureStatus.CANCELLED:
            print("\nTransaction annulée par l'utilisateur\n")

        else:
            print("\nTransaction réussie\n")
            print(f"\nDonnées finales : {data}\n")

    async def finalise(resp: FedapayPay):
        # Etape 2 : Finalisation du paiement
        print("\nFinalisation de paiement...\n")
        future_event_status, data = await fedapay.fedapay_finalise(resp.id_transaction)
        await run_after_finalise(future_event_status, data)

    async def payment_callback(payment: PaymentHistory):
        print(f"Callback de paiement reçu : {payment.__dict__}")

    async def webhook_callback(webhook_data: WebhookHistory):
        print(f"Webhook reçu : {webhook_data.__dict__}")

    print("\nTest singleton\n")
    instance1 = FedapayConnector(
        use_listen_server=True,
        listen_server_port=8000,
        listen_server_endpoint_name="utils/webhooks",
    )
    instance2 = FedapayConnector(use_listen_server=False, listen_server_port=8000)

    if instance1 is instance2:
        print("\nLe module se comporte comme un singleton.\n")
    else:
        print("\nLe module ne se comporte pas comme un singleton.\n")

    try:
        print("Tests fonctionnels\n")

        # Initialisation de l'instance FedapayConnector
        fedapay = instance1
        fedapay.set_payment_callback_function(payment_callback)
        fedapay.set_webhook_callback_function(webhook_callback)
        fedapay.set_on_persited_listening_processes_loading_finished_callback(
            run_after_finalise
        )

        # lancement de la restauration des processus d'écoute
        await fedapay.load_persisted_listening_processes()

        # Démarrage du serveur d'ecoute de webhook
        fedapay.start_webhook_server()

        # Configuration du paiement
        setup = PaiementSetup(
            pays=Pays.benin,
            method=MethodesPaiement.mtn_open,
            type_paiement=TypesPaiement.SANS_REDIRECTION,
        )

        setup1 = PaiementSetup(
            pays=Pays.benin,
            type_paiement=TypesPaiement.AVEC_REDIRECTION,
        )

        client = UserData(
            nom="ASSOGBA",
            prenom="Dayane",
            email="assodayane@gmail.com",
            tel="0162019988",
        )

        ""  # Étape 1 : Initialisation du paiement
        print("\nInitialisation du paiement sans redirection...\n")
        resp = await fedapay.fedapay_pay(
            setup=setup, client_infos=client, montant_paiement=100
        )
        print(f"\nRéponse de l'initialisation : {resp.model_dump()}\n")

        # Vérification si l'initialisation a réussi
        if not resp.id_transaction:
            print("\nErreur : L'initialisation de la transaction a échoué.\n")
            return ""

        print("\nInitialisation du paiement avec redirection...\n")
        resp1 = await fedapay.fedapay_pay(
            setup=setup1, client_infos=client, montant_paiement=200
        )
        print(f"\nRéponse de l'initialisation : {resp1.model_dump()}\n")

        # Vérification si l'initialisation a réussi
        if not resp1.id_transaction:
            print("\nErreur : L'initialisation de la transaction a échoué.\n")
            return

        task1 = asyncio.create_task(finalise(resp))
        task2 = asyncio.create_task(finalise(resp1))

        end_result = await asyncio.gather(task1, task2)

        print(end_result)

    except Exception as e:
        print(f"Une erreur s'est produite : {e}")

    finally:
        # Nettoyage et arrêt du serveur d'écoute
        await instance1.shutdown_cleanup()


if __name__ == "__main__":
    asyncio.run(main())
