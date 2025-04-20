from fedapay_connector import Pays, MethodesPaiement, FedapayConnector, PaiementSetup, UserData
import asyncio


async def main():
    try:
        print("\nTest singleton\n")
        instance1 = FedapayConnector()
        instance2 = FedapayConnector()

        if instance1 is instance2:
            print("\nLe module se comporte comme un singleton.\n")
        else:
            print("\nLe module ne se comporte pas comme un singleton.\n")

        print("Tests fonctionnels\n")

        # Initialisation de l'instance FedapayConnector
        fedapay = FedapayConnector()

        # Configuration du paiement
        setup = PaiementSetup(pays=Pays.benin, method=MethodesPaiement.mtn_open)
        client = UserData(nom="ASSOGBA", prenom="Dayane", email="assodayane@gmail.com", tel="0162019988")

        # Étape 1 : Initialisation du paiement
        print("\nInitialisation du paiement...\n")
        resp = await fedapay.Fedapay_pay(setup=setup, client_infos=client, montant_paiement=100)
        print(f"\nRéponse de l'initialisation : {resp}\n")

        # Vérification si l'initialisation a réussi
        if not resp.get("id_transaction_fedapay"):
            print("\nErreur : L'initialisation de la transaction a échoué.\n")
            return

        # Étape 2 : Vérification du statut de la transaction
        print("\nVérification du statut de la transaction...\n")
        status = await fedapay.Check_transaction_status(resp.get("id_transaction_fedapay"))
        print(f"\nStatut de la transaction : {status}\n")

    except Exception as e:
        print(f"Une erreur s'est produite : {e}")

if __name__ == "__main__":
    asyncio.run(main())