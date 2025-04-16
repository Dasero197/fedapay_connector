# FedaPay Connector

FedaPay Connector est un connecteur asynchrone pour interagir avec l'API FedaPay. Il permet de gérer les paiements, les statuts des transactions, et les webhooks.

## Installation


```bash
pip install fedapay_connector

```
## Utilisation

```python
from fedapay_connector import FedapayConnector, PaiementSetup, UserData, Pays, MethodesPaiement
import asyncio

async def main():
    fedapay = FedapayConnector()
    setup = PaiementSetup(pays=Pays.benin, method=MethodesPaiement.moov)
    client = UserData(nom="john", prenom="doe", email="myemail@domain.com", tel="+22964000001")

    # Initialisation du paiement
    resp = await fedapay.Fedapay_pay(setup=setup, client_infos=client, montant_paiement=1000)
    print(resp)

    # vous pouver appeler la methode Fedapay_finalise si vous avez déja creer un endpoint dans votre api pour recevoir les webhook de fedapay (voir la methode Save_webhook_data et sa documentation)

    # si vous ne pouvez pas utiliser Fedapay Finalise vous devrez faire du polling en utilisant la methode Check_transaction_status et en analysant sa reponse en fonction du status rechercher le tout dans une boucle
    
    status = await fedapay.Check_transaction_status(resp.get("id_transaction_fedapay"))
    print(status)

if __name__ == "__main__":
    asyncio.run(main())
```
## Licence

Ce projet est sous licence GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later). Consultez le fichier LICENSE pour plus d'informations.