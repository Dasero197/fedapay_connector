from fedapay_connector import Pays, FedapayPay, MethodesPaiement, TypesPaiement, FedapayConnector, PaiementSetup, UserData, EventFutureStatus, PaymentHistory, WebhookHistory
import asyncio


async def main():
    try:
        async def finalise(resp:FedapayPay):
            # Etape 2 : Finalisation du paiement
            print("\nFinalisation de paiement...\n")
            future_event_status, data = await fedapay.fedapay_finalise(resp.id_transaction)

            if future_event_status == EventFutureStatus.TIMEOUT:
                #Vérification manuelle du statut de la transaction
                print("\nLa transaction a expiré. Vérification manuelle du statut...\n")
                print("\nVérification manuelle du statut de la transaction...\n")
                status = await fedapay.fedapay_check_transaction_status(resp.id_transaction)
                print(f"\nStatut de la transaction : {status.model_dump()}\n")
            
            elif future_event_status == EventFutureStatus.CANCELLED:
                print("\nTransaction annulée par l'utilisateur\n")

            else:
                print("\nTransaction réussie\n")
                print(f"\nDonnées finales : {data}\n")


        async def payment_callback(data:PaymentHistory):
            print(f"Callback de paiement reçu : {data.__dict__}")

        async def webhook_callback(data:WebhookHistory):
            print(f"Webhook reçu : {data.__dict__}")

        print("\nTest singleton\n")
        instance1 = FedapayConnector(use_listen_server= True)
        instance2 = FedapayConnector(use_listen_server= False)

        if instance1 is instance2:
            print("\nLe module se comporte comme un singleton.\n")
        else:
            print("\nLe module ne se comporte pas comme un singleton.\n")

        print("Tests fonctionnels\n")

        # Initialisation de l'instance FedapayConnector
        fedapay = instance1
        fedapay.set_payment_callback_function(payment_callback)
        fedapay.set_webhook_callback_function(webhook_callback)

        fedapay.start_webhook_server()

        # Configuration du paiement
        setup = PaiementSetup(pays=Pays.benin, method=MethodesPaiement.mtn_open)
        setup1 = PaiementSetup(pays=Pays.benin, method=MethodesPaiement.mtn_open, type_paiement= TypesPaiement.AVEC_REDIRECTION)
        
        client = UserData(nom="ASSOGBA", prenom="Dayane", email="assodayane@gmail.com", tel="0162019988")

        ""# Étape 1 : Initialisation du paiement
        print("\nInitialisation du paiement sans redirection...\n")
        resp = await fedapay.fedapay_pay(setup=setup, client_infos=client, montant_paiement=100)
        print(f"\nRéponse de l'initialisation : {resp.model_dump()}\n")

        # Vérification si l'initialisation a réussi
        if not resp.id_transaction:
            print("\nErreur : L'initialisation de la transaction a échoué.\n")
            return""
        
        print("\nInitialisation du paiement avec redirection...\n")
        resp1 = await fedapay.fedapay_pay(setup=setup1, client_infos=client, montant_paiement=200)
        print(f"\nRéponse de l'initialisation : {resp1.model_dump()}\n")

        # Vérification si l'initialisation a réussi
        if not resp1.id_transaction:
            print("\nErreur : L'initialisation de la transaction a échoué.\n")
            return

        task1 = asyncio.create_task(finalise(resp))
        task2 = asyncio.create_task(finalise(resp1))


        g = await asyncio.gather(task1, task2)

        print(g)

    except Exception as e:
        print(f"Une erreur s'est produite : {e}")

if __name__ == "__main__":
    asyncio.run(main())