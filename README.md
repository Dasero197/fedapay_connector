# FedaPay Connector

![PyPI version](https://img.shields.io/pypi/v/fedapay_connector)
![Python versions](https://img.shields.io/pypi/pyversions/fedapay_connector)
![License](https://img.shields.io/pypi/l/fedapay_connector)
![Downloads](https://img.shields.io/pypi/dm/fedapay_connector)

Un client asynchrone robuste pour l'API FedaPay, offrant une gestion automatisée des paiements avec support complet des webhooks.

## ✨ Caractéristiques

- 🔄 **Pattern Singleton** - Une seule instance partagée dans toute l'application
- ⚡ **Entièrement Asynchrone** - Performances optimales avec asyncio
- 🔒 **Sécurisé** - Validation des signatures et gestion sécurisée des webhooks
- 💾 **Persistence Automatique** - Sauvegarde et restauration des transactions
- 🎯 **Callbacks Personnalisables** - Hooks pour tous les événements
- 🚀 **Simple à Utiliser** - API intuitive et documentation complète
- 🛠️ **Module bas niveau pour controle granulaire** - Pour les dev qui veulent avoir plus de controle

## Installation

### Via pip
```bash
pip install fedapay_connector
```

### Via poetry
```bash
poetry add fedapay_connector
```

## 🛠️ Configuration

### Prérequis

- Python 3.9+
- Un compte FedaPay avec les clés API
- Pour le serveur webhook : une URL accessible publiquement pointant vers votre serveur (via ngrok, un reverse proxy, etc.)

### Variables d'Environnement

| Variable | Description | Requis | Défaut |
|----------|-------------|--------|---------|
| `FEDAPAY_API_KEY` | Clé API FedaPay | ✅ | - |
| `FEDAPAY_API_URL` | URL API (sandbox/production) | ✅ | - |
| `FEDAPAY_AUTH_KEY` | Clé secrète webhook | ✅ | - |
| `FEDAPAY_ENDPOINT_NAME` | Endpoint webhook | ❌ | `webhooks` |
| `FEDAPAY_DB_URL` | URL sqlalchemy base de données  | ❌ | `sqlite:///fedapay_connector_persisted_data/processes.db` |

### Exemple de .env
```env
FEDAPAY_API_KEY=fp_key_live_123456789
FEDAPAY_API_URL=https://api.fedapay.com
FEDAPAY_AUTH_KEY=webhook_secret_123456789
FEDAPAY_ENDPOINT_NAME=webhooks
```

## 📚 Guide d'Utilisation 

### Modes d'Utilisation module FedapayConnector

1. **Mode Simple** (non recommandé)
   - Polling manuel du statut
   - Sans gestion des webhooks

2. **Mode Serveur Intégré** (recommandé)
   - Serveur webhook intégré
   - Gestion automatique des événements
   - Parfait pour une apllication python hors context d'API

3. **Mode Serveur Intégré (options avancées)** (recommandé)
   - Serveur webhook intégré
   - Gestion automatique des événements
   - Sauvegarde et restauration automatique des processus découtes apres arrêt ou redemarrage de l'app
   - Parfait pour une apllication python hors context d'API

4. **Mode API Existante** 
   - Intégration avec FastAPI/Django/etc
   - Gestion personnalisée des webhooks

#### 1. Mode Simple 

```python
from fedapay_connector import Pays, MethodesPaiement, FedapayConnector, PaiementSetup, UserData, EventFutureStatus, PaymentHistory, WebhookHistory
import asyncio

async def main():
    # Creation de l'instance Fedapay Connector
    fedapay = FedapayConnector(use_listen_server= False) 

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

    while True:
    # vérifier le resultat manuellement par polling
    status = await fedapay.fedapay_check_transaction_status(resp.id_transaction)
    if status.status == TransactionStatus.created or status.status == TransactionStatus.pending:
        await asyncio.sleep(0.1)
    else:
        break

if __name__ == "__main__":
    asyncio.run(main())
```

#### 2. Mode Serveur Intégré

Cette option nécéssite que vous ayez un reverse proxy pointant sur votre machine au port d'ecoute configurer pour le serveur
(défaut : 3000) depuis une url qui sera utiliseée pour la configuration des webhook sur votre panel fedapay. 
[lien doc fedapay](https://docs.fedapay.com/integration-api/fr/webhooks-fr)

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
        # La vérification manuelle du statut de la transaction se fait automatiquement si timeout donc si timeout est levé pas besoin de revérifier manuellement le status.

        print("\nLa transaction a expiré.\n")

    elif status == EventFutureStatus.CANCELLED:
        print("\nTransaction annulée par l'utilisateur\n")

    elif status == EventFutureStatus.CANCELLED_INTERNALLY:
            print("\nTransaction annulée en interne -- probable redemarrage ou arret de l'application\n")
    

if __name__ == "__main__":
    asyncio.run(main())
```


#### 3. Mode Serveur Intégré (options avancées)

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
    
    async def run_after_finalise(
        status: EventFutureStatus, data: list[WebhookHistory] | None
    ):
        # s'execute après la récupération d'écoute perdue une fois que la reponse de fedapay est reçue
        # ou que le timeout naturel survient
        if status == EventFutureStatus.RESOLVED:
            print("\nTransaction réussie\n")
            print(f"\nDonnées finales : {data}\n")

            # ATTENTION :  Ce cas indique le reception d'une webhook valide et la clôture de la transaction mais ne veut pas systématiquement dire due l'opération à été approuvée

            # Il faudra implementer par la suite votre gestion des webhook pour la validation ou tout autre traitement du paiement effectuer à partir de la liste d'objet WebhookTransaction reçu.

        elif status == EventFutureStatus.TIMEOUT:
            # La vérification manuelle du statut de la transaction se fait automatiquement si timeout donc si timeout est levé pas besoin de revérifier manuellement le status sur le coup.

            print("\nLa transaction a expiré.\n")

        elif status == EventFutureStatus.CANCELLED:
            print("\nTransaction annulée par l'utilisateur\n")

        elif status == EventFutureStatus.CANCELLED_INTERNALLY:
            print("\nTransaction annulée en interne -- probable redemarrage ou arret de l'application\n")

    # Creation de l'instance Fedapay Connector
    fedapay = FedapayConnector(use_listen_server= True) 

    # Configuration des callbacks
    fedapay.set_payment_callback_function(payment_callback) # executer a chaques appels reussi a fedapay_pay()
    fedapay.set_webhook_callback_function(webhook_callback) # executer à la réception de webhooks fedapay valides
    fedapay.set_on_persited_listening_processes_loading_finished_callback(run_after_finalise) 
    # éxectuer lors de la récupération des ecoutes d'event fedapay perduent lors d'un potentiel 
    # redemarrage de l'app pendant que des ecoutes sont actives.

    # lancement de la restauration des processus d'écoute
    await fedapay.load_persisted_listening_processes()

    # Démarrage du listener interne
    fedapay.start_webhook_server()

    # Configuration paiement
    setup = PaiementSetup(
        pays=Pays.benin,
        method=MethodesPaiement.moov
    )
    
    client = UserData(
        nom="Doe",
        prenom="John",
        email="john@example.com",
        tel="0164000001"
    )

    # Exécution paiement
    resp = await fedapay.fedapay_pay(
        setup=setup,
        client_infos=client,
        montant_paiement=1000,
        payment_contact="0162626262"
    )

    # Attente résultat
    status, webhooks = await fedapay.fedapay_finalise(resp.transaction.id)


if __name__ == "__main__":
    asyncio.run(main())
```

#### 4. Mode API Existante (Intégration FastAPI ou framework similaire)

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
    await fedapay.shutdown_cleanup()

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

### Modes d'Utilisation module Integration (Utilisation avancée)

Pour les utilisateurs qui souhaitent un contrôle plus granulaire des appels HTTP vers l'API FedaPay (CRUD complet sur Transactions, Events, Balances, Currencies, Logs, Webhooks), utilisez la classe `Integration` fournie dans le package.

Principales caractéristiques :
- Fournit un point d'entrée unique pour les services bas-niveau : `Transactions`, `Balances`, `Currencies`, `Events`, `Logs`, `Webhooks`.
- Utilisée quand vous ne voulez pas du workflow automatique (Listeners / Futures) géré par `FedapayConnector` et préférez appeler manuellement les endpoints.

Constructeur :
- `Integration(api_url: str = os.getenv("FEDAPAY_API_URL"), logger: logging.Logger = None, default_api_key: Optional[str] = os.getenv("FEDAPAY_API_KEY"))`
- Remarque importante : `api_url` et `default_api_key` sont requis (ou doivent être fournis via les variables d'environnement). Si l'un d'eux manque, le constructeur lèvera `ValueError`.

Exemple d'utilisation basique :

```python
import asyncio
from fedapay_connector.integration import Integration

async def main():
    integ = Integration()  # lit FEDAPAY_API_URL et FEDAPAY_API_KEY depuis l'env

    # Récupérer une transaction par ID Fedapay
    tx = await integ.get_transaction_by_fedapay_id("12345")
    print(tx)

    # Créer une transaction (voir models.PaiementSetup / UserData)
    setup = PaiementSetup(...)
    client = UserData(...)
    new_tx = await integ.create_transaction(setup, client, montant_paiement=1000)

    # Récupérer lien / token
    token = await integ.get_transaction_link(new_tx.id)

    # Lister les événements
    events = await integ.get_all_events(params={})

asyncio.run(main())
```

Notes pratiques :
- Les méthodes `Integration` renvoient les modèles Pydantic présents dans `fedapay_connector.models` (ex: `Transaction`, `TransactionListResponse`, `EventResponse`).
- Pour les tests, mockez les méthodes des services internes (par ex. `Transactions._get_transaction_by_fedapay_id`) lorsque vous vérifiez la logique métier dépendante du réseau.
- `Integration` est synchrone avec l'API asynchrone (utilise `aiohttp` en interne) — appelez-le depuis une coroutine ou via `asyncio.run()`.


## Fonctionnalités Avancées

### Gestion des Webhooks

```python
# 1. Serveur Intégré
fedapay = FedapayConnector(
    use_listen_server=True,
    listen_server_port=3000,
    listen_server_endpoint_name="webhooks"
)
fedapay.start_webhook_server()  # convenience wrapper -> calls `WebhookServer.start_webhook_listenning()`

# 2. Intégration API Existante
fedapay = FedapayConnector(use_listen_server=False)
await fedapay.fedapay_save_webhook_data(webhook_data)
```

Cycle de vie du serveur interne:
- Le serveur interne est lancé dans un thread d'arrière-plan. FedapayConnector expose :
    - `start_webhook_server()` -> Démarre le serveur interne .
    - `shutdown_cleanup()` -> méthode asynchrone qui annule les futures d'événements en attente, attend les tâches de rappel (avec un délai d'attente) et arrête le serveur webhook via `stop_webhook_listenning()`.

Recommendation: call `await fedapay.shutdown_cleanup()` from your application's shutdown handler (FastAPI lifespan or SIGTERM) to ensure persisted listeners and callback tasks are cleaned up correctly.

### Callbacks Personnalisés

```python
async def on_payment(payment: PaymentHistory):
    """Appelé après chaque paiement"""
    print(f"Nouveau paiement: {payment.transaction.id}")
    
async def on_webhook(webhook: WebhookHistory):
    """Appelé pour chaque webhook"""
    print(f"Webhook reçu: {webhook.name}")

async def run_after_finalise(
    status: EventFutureStatus, data: list[WebhookHistory] | None
):
    """Appelé après la résolution d'écoutes récupérées """
    
    if status == EventFutureStatus.RESOLVED:
        print("\nTransaction réussie\n")
        print(f"\nDonnées finales : {data}\n")

    elif status == EventFutureStatus.TIMEOUT:
        print("\nLa transaction a expiré.\n")

    elif status == EventFutureStatus.CANCELLED:
        print("\nTransaction annulée par l'utilisateur\n")
    
    elif future_event_status == EventFutureStatus.CANCELLED_INTERNALLY:
            print("\nTransaction annulée en interne -- probable redemarrage ou arret de l'application\n")

fedapay.set_payment_callback_function(on_payment)
fedapay.set_webhook_callback_function(on_webhook)
fedapay.set_on_persited_listening_processes_loading_finished_callback(run_after_finalise)
```

### Persistence et Restauration

Le module gère automatiquement :
- Sauvegarde des transactions en cours
- Restauration après redémarrage
- Reprise des écouteurs interrompus
- Synchronisation avec FedaPay

## 🔧 Dépannage

### Problèmes Courants

1. **Les webhooks ne sont pas reçus**
   - Vérifier l'URL configurée dans FedaPay
   - Vérifier la clé secrète webhook

2. **Erreurs de timeout**
   - Augmenter la valeur du timeout
   - Vérifier la connexion réseau
   - Consulter les logs pour plus de détails

## Contribution

Les contributions sont les bienvenues!

## Licence

Ce projet est sous licence GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later). Consultez le fichier LICENSE pour plus d'informations.

## 🔒 Sécurité

- Ne jamais exposer les clés API
- Toujours valider les signatures webhook
- Utiliser HTTPS en production
- Implémenter des timeouts appropriés