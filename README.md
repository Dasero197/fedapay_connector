# FedaPay Connector

FedaPay Connector est un connecteur asynchrone pour interagir avec l'API FedaPay. Il permet de gérer les paiements, les statuts des transactions, et les webhooks.

## Installation


```bash
pip install fedapay_connector

```
## Utilisation

from fedapay_connector import FedapayConnector, PaiementSetup, UserData, Pays, MethodesPaiement
import asyncio

async def main():
    fedapay = FedapayConnector()
    setup = PaiementSetup(pays=Pays.benin, method=MethodesPaiement.moov)
    client = UserData(nom="john", prenom="doe", email="myemail@domain.com", tel="+22964000001")

    # Initialisation du paiement
    resp = await fedapay.Fedapay_pay(setup=setup, client_infos=client, montant_paiement=1000)
    print(resp)

    # Vérification du statut
    status = await fedapay.Check_Fedapay_status(resp.get("id_transaction_fedapay"))
    print(status)

if __name__ == "__main__":
    asyncio.run(main())

## Licence

Ce projet est sous licence GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later). Consultez le fichier LICENSE pour plus d'informations.