# FedaPay Connector

FedaPay Connector est un client asynchrone Singleton conçu pour interagir avec l'API FedaPay. Il permet de gérer les paiements avec et sans redirection coté serveur, les statuts des transactions manuellement et automatiquement avec une webhooks.

## Installation


```bash
pip install fedapay_connector

```
## Utilisation

```python
from fedapay_connector import Pays, MethodesPaiement, FedapayConnector, PaiementSetup, UserData, EventFutureStatus, PaymentHistory, WebhookHistory
import asyncio

async def main():

    # Creation des callbacks
    async def payment_callback(data:PaymentHistory):
            print(f"Callback de paiement reçu : {data.__dict__}")

    async def webhook_callback(data:WebhookHistory):
        print(f"Webhook reçu : {data.__dict__}")

    # Creation de l'instance Fedapay Connector
    fedapay = FedapayConnector(listen_for_webhook= True) 

    # Configuration des callbacks
    fedapay.set_payment_callback_function(payment_callback)
    fedapay.set_webhook_callback_function(webhook_callback)

    # Démarrage du listener interne
    fedapay.start_webhook_server()

    # Configuration du paiement
    setup = PaiementSetup(pays=Pays.benin, method=MethodesPaiement.mtn_open)
    client = UserData(nom="john", prenom="doe", email="myemail@domain.com", tel="+22962626262")

    # Initialisation du paiement
    resp = await fedapay.fedapay_pay(setup=setup, client_infos=client, montant_paiement=1000)
    print(resp.model_dump())

    # Finalisation du paiement
    future_event_status, data_list = await fedapay.fedapay_finalise(resp.id_transaction)
        if future_event_status == EventFutureStatus.TIMEOUT:
            ### Vérification manuelle du statut de la transaction si webhook non reçu
            print("\nLa transaction a expiré. Vérification manuelle du statut...\n")
            print("\nVérification manuelle du statut de la transaction...\n")
            status = await fedapay.fedapay_check_transaction_status(resp.id_transaction)
            print(f"\nStatut de la transaction : {status.model_dump()}\n")

            ### Cas d'annulation par l'utilisateur
        elif future_event_status == EventFutureStatus.CANCELLED:
            print("\nTransaction annulée par l'utilisateur\n")

            ### Cas de reception d'une webhook valide
        else:
            ### On a future_event_status == EventFutureStatus.RESOLVED dans ce cas ce qui indique la reception d'une webhook valide PAS QUE LE PAIEMENT AI ETE APROUVER.
            ### Il faudra implementer par la suite votre gestion des webhook pour la validation ou tout autre traitement du paiement effectuer à partir de la liste d'objet WebhookTransaction reçu.
            print("\nTransaction réussie\n")
            print(f"\nDonnées finales : {data_list}\n")

if __name__ == "__main__":
    asyncio.run(main())
```
## Utilisation avec FastAPI ou framework similaire

Dans des cas d'usage comme pour un backend FastAPI vous devrez faire l'initialisation du module dans le async context au demarrage de FastAPI puis l'utiliser directement dans vos point de terminaisons pour le traitement des transaction.

```python

... code du fichier main.py ...

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Creation de l'instance Fedapay Connector
    fedapay = FedapayConnector(listen_for_webhook= False) # 'listen_for_webhook' a False parce que inutile dans une contexte FastAPI, construiser directement votre endpoint et utiliser 'fedapay_save_webhook_data' pour communiquer les event a fedapay connector

    # importer ou definissez prealablement les callabacks si voulu
    # Configuration des callbacks
    fedapay.set_payment_callback_function(payment_callback)
    fedapay.set_webhook_callback_function(webhook_callback)

    yield
    #permet d'annuler tous future event en attente non reçu ou non timeout à l'arret de FastAPI
    fedapay.cancel_all_future_event("backend server is stopping or restarting")

app = FastAPI(lifespan=lifespan)

... suite de votre code ...
```

Si les methodes de paiement que vous souhaiter utilisés ne sont pas disponibles en paiement sans redirection vous devrez recupérer le paiement link et le retourner au front end pour affichage dans une webview ou un element similaire pour finalisation par l'utilisateur.
Le satut sera toutefois toujours capturer par le backend directement donc il n'est pas neccessaire de le recupérer coté client. 


## Configuration

Fedapay Connector à besoin de certaines variable environement qui peuvent toutes fois etre passées lors de son execution si non presente en variable environement (fichier .env de votre projet).

Il s'agit de:

- API_KEY : Clé api disponible dans l'onglet  Api sur votre pannel Fedapay

- API_URL : Url api fedapay (sandbox ou live)

- FEDAPAY_AUTH_KEY : Clé secrete de la webhook configuré disposible dans votre pannel Fedapay

- ENDPOINT_NAME : Nom attendu pour le point terminaison exposé par le serveur interne

Aussi vous aurez besoin d'ajouter la clé "agregateur" associé à la valeur "Fedapay" si vous utiliser le serveur interne pour recevoir les webhooks.

Par defaut le serveur interne utilise le port 3000 qui peut etre modifier lors de la creation de l'instance.

Pour que Fedapay puisse accéder à votre serveur interne vous devrez exposé le port utiliser par ce dernier dans vos regles de parfeu et soit herberger votre application sur un serveur cloud ou utilisé d'autre solution pour rendre votre machine accessible depuis internet.

## Licence

Ce projet est sous licence GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later). Consultez le fichier LICENSE pour plus d'informations.