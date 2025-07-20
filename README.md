# FedaPay Connector

FedaPay Connector est un client asynchrone Singleton avancé, conçu pour interagir avec l'API FedaPayoffrant une gestion automatisée des paiements et des webhooks avec persistence des événements.

## Installation

### Via pip
```bash
pip install fedapay_connector
```

### Via poetry
```bash
poetry add fedapay_connector
```

## Configuration

### Variables d'Environnement

```bash
# Requis
FEDAPAY_API_KEY="votre_cle_api"               # Clé API FedaPay
FEDAPAY_API_URL="url_api"                     # URL API (sandbox/production)
FEDAPAY_AUTH_KEY="webhook_secret"             # Clé secrète webhook

# Optionnel
FEDAPAY_ENDPOINT_NAME="webhooks"              # Endpoint webhook (défaut: webhooks)
FEDAPAY_DB_URL="sqlite:///processes.db"       # URL base de données (défaut: SQLite)
```

### Exemple de .env
```env
FEDAPAY_API_KEY=fp_key_live_123456789
FEDAPAY_API_URL=https://api.fedapay.com
FEDAPAY_AUTH_KEY=webhook_secret_123456789
FEDAPAY_ENDPOINT_NAME=webhooks
```

## Utilisation

### 1. Paiement Simple

```python
from fedapay_connector import Pays, MethodesPaiement, FedapayConnector, PaiementSetup, UserData, EventFutureStatus, PaymentHistory, WebhookHistory
import asyncio

async def main():

    # Creation des callbacks
    async def payment_callback(data:PaymentHistory):
        # s'execute chaque fois qu'un nouveau paiement est initialisé avec fedapay_pay()
            print(f"Callback de paiement reçu : {data.__dict__}")

    async def webhook_callback(data:WebhookHistory):
        # s'execute chaque fois qu'un nouveau webhook est reçu de fedapay
        print(f"Webhook reçu : {data.__dict__}")

    # Creation de l'instance Fedapay Connector
    fedapay = FedapayConnector(use_listen_server= True) 

    # Configuration des callbacks
    fedapay.set_payment_callback_function(payment_callback) # executer a chaques appels reussi a fedapay_pay()
    fedapay.set_webhook_callback_function(webhook_callback) # executer à la réception de webhooks fedapay valides
    fedapay.set_on_persited_listening_processes_loading_finished_callback(run_after_finalise) # éxectuer lors de la récupération des ecoutes d'event fedapay perduent lors d'un potentiel redemarrage de l'app pendant que des ecoutes sont actives.

    # lancement de la restauration des processus d'écoute
    await fedapay.load_persisted_listening_processes()

    # Démarrage du listener interne
    fedapay.start_webhook_server()

    # Configuration paiement
    setup = PaiementSetup(
        pays=Pays.benin,
        method=MethodesPaiement.mtn_open
    )
    
    client = UserData(
        nom="Doe",
        prenom="John",
        email="john@example.com",
        tel="0162626262"
    )

    # Exécution paiement
    resp = await fedapay.fedapay_pay(
        setup=setup,
        client_infos=client,
        montant_paiement=1000,
        payment_contact="0162626262"
    )

    # Attente résultat
    status, webhooks = await fedapay.fedapay_finalise(resp.id_transaction)

    
    if status == EventFutureStatus.RESOLVED:
        print("\nTransaction réussie\n")
        print(f"\nDonnées finales : {webhooks}\n")

        # ATTENTION :  Ce cas indique le reception d'une webhook valide et la clôture de la transaction mais ne veut pas systématiquement dire due l'opération à été approuvée

        # Il faudra implementer par la suite votre gestion des webhook pour la validation ou tout autre traitement du paiement effectuer à partir de la liste d'objet WebhookTransaction reçu.

    elif status == EventFutureStatus.TIMEOUT:
        # La vérification manuelle du statut de la transaction se fait automatiquement si timeout donc si timeout est levé pas besoin de revérifier manuellement le status sur le coup.

        print("\nLa transaction a expiré.\n")

    elif status == EventFutureStatus.CANCELLED:
        print("\nTransaction annulée par l'utilisateur\n")
    

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Intégration FastAPI ou framework similaire

Dans des cas d'usage comme pour un backend FastAPI vous devrez faire l'initialisation du module dans le lifespan au demarrage de FastAPI puis l'utiliser directement dans vos logiques métiers pour le traitement des transaction.

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fedapay_connector import FedapayConnector


... code du fichier main.py ...

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Creation de l'instance Fedapay Connector
    fedapay = FedapayConnector(use_listen_server= False) 

    # importer ou definissez prealablement les callabacks si voulu
    # Configuration des callbacks
    fedapay.set_payment_callback_function(payment_callback) # executer a chaques appels reussi a fedapay_pay()
    fedapay.set_webhook_callback_function(webhook_callback) # executer à la réception de webhooks fedapay valides
    fedapay.set_on_persited_listening_processes_loading_finished_callback(run_after_finalise) # éxectuer lors de la récupération des ecoutes d'event fedapay perduent lors d'un potentiel redemarrage de l'app pendant que des ecoutes sont actives.

    # lancement de la restauration des processus d'écoute
    await fedapay.load_persisted_listening_processes()

    yield

    #permet un arret propre de fedapay connector
    fedapay.shutdown_cleanup()

app = FastAPI(lifespan=lifespan)

@app.post("/webhooks/fedapay")
async def fedapay_webhook(request: Request):
    payload = await request.body()
    headers = request.headers
    
    # Validation signature
    signature = headers.get("x-fedapay-signature")
    FedapayConnector().verify_signature(payload, signature)
    
    # Traitement webhook
    event = await request.json()
    await FedapayConnector().fedapay_save_webhook_data(event)
    
    return {"status": "success"}
    
... suite de votre code ...
```

Si les methodes de paiement que vous souhaiter utilisés ne sont pas disponibles en paiement sans redirection vous devrez recupérer le paiement link et le retourner au front end pour affichage dans une webview ou un element similaire pour finalisation par l'utilisateur.
Le satut sera toutefois toujours capturer par le backend directement donc il n'est pas neccessaire de le recupérer coté client. 

## Fonctionnalités Avancées

### Gestion des Webhooks

```python
# 1. Serveur Intégré
fedapay = FedapayConnector(
    use_listen_server=True,
    listen_server_port=3000,
    listen_server_endpoint_name="webhooks"
)
fedapay.start_webhook_server()

# 2. Intégration API Existante
fedapay = FedapayConnector(use_listen_server=False)
await fedapay.fedapay_save_webhook_data(webhook_data)
```

### Callbacks Personnalisés

```python
async def on_payment(payment: PaymentHistory):
    """Appelé après chaque paiement"""
    print(f"Nouveau paiement: {payment.id}")
    
async def on_webhook(webhook: WebhookHistory):
    """Appelé pour chaque webhook"""
    print(f"Webhook reçu: {webhook.name}")

fedapay.set_payment_callback_function(on_payment)
fedapay.set_webhook_callback_function(on_webhook)
```

### Persistence et Restauration

Le module gère automatiquement :
- Sauvegarde des transactions en cours
- Restauration après redémarrage
- Reprise des écouteurs interrompus
- Synchronisation avec FedaPay

### Gestion des Erreurs

```python
try:
    status = await fedapay.fedapay_check_transaction_status(transaction_id)
except FedapayAPIError as e:
    print(f"Erreur API: {e}")
except SignatureError as e:
    print(f"Signature invalide: {e}")
except TimeoutError as e:
    print(f"Timeout: {e}")
```

## Documentation Complète

Pour une documentation détaillée incluant:
- Guides avancés
- Référence API complète
- Exemples détaillés
- Bonnes pratiques

Visitez [la documentation complète](https://fedapay-connector.readthedocs.io/).

## Contribution

Les contributions sont les bienvenues! Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour les détails.

## Licence

Ce projet est sous licence GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later). Consultez le fichier LICENSE pour plus d'informations.