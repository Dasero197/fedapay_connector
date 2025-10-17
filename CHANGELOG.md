# Notes de version de fedapay-connector

## Version 2.0.0 (2025-10-17)

### Résumé

Version majeure — **breaking changes** : refonte importante du connecteur asynchrone, modifications des modèles de données et ajout d’un module d’intégration directe (`Integration`). Cette version n’est **pas compatible** avec la série 1.x (notamment 1.3.5). Migration requise.

---

### Breaking Changes (changements cassants)

* Refonte API publique : plusieurs signatures et emplacements de modules ont changé (imports, noms de classes/énumérations). Adapter les imports et appels (ex. `integrations`, `models.models`, `Transactions`...).
* Réorganisation des modules : `Integration` est maintenant la façade recommandée pour l'accès direct à l'API (utilisateurs avancés). Les anciens chemins d’import peuvent ne plus fonctionner.
* Les modèles de réponse de FedaPay ont changé pour fournir plus d'informations et rester cohérents avec les données retournées par FedaPay.
* Schéma de persistence : la structure de stockage des processus d’écoute a été modifiée (nouveau modèle/table). Les bases existantes doivent être migrées ou recréées.

---

### Nouvelles fonctionnalités

* **Module `Integration`** : façade unifiée pour un accès granulaire à l’API FedaPay (Transactions, Balances, Currencies, Events, Logs, Webhooks). Permet CRUD complet et opérations avancées sans les workflows automatiques du connecteur. (`integration.py`) **Ne supporte pas encore les opérations de payout.**
* **Annulation des transactions** : méthode `fedapay_cancel_transaction` dans `FedapayConnector` révisée pour tenter d’annuler les transactions côté FedaPay avant d’effectuer une annulation interne. Elle renvoie des erreurs claires indiquant si l’échec est dû à un état final (transaction déjà non-pending) ou à une erreur inattendue. (`connector.py`)
* **Validation Pydantic renforcée** : les webhooks et entités API sont validés (`WebhookTransaction.model_validate(...)`, `PaiementSetup`, `UserData`, etc.).
* **Cleaner shutdown / cleanup** : `shutdown_cleanup()` — annulation des futures, attente contrôlée des callbacks avec timeout, arrêt propre du serveur webhook intégré.
* **Amélioration de la journalisation** : configuration plus claire du logging (console vs fichier) et messages plus structurés.

---

### Améliorations & optimisations

* Meilleure résilience des processus d’écoute : rechargement des processus persistés au démarrage et vérification active du statut de chaque transaction côté FedaPay avant de rétablir l’écoute.
* Gestion asynchrone des callbacks : verrou (`_callback_lock`), suivi des tâches `_callback_tasks`, protection et logging des exceptions dans les callbacks (`_handle_payment_callback_exception`, `_handle_webhook_callback_exception`).
* Ajout / standardisation des statuts finaux pris en charge (incluant `expired` ; gestion plus robuste des cas `approved`, `declined`, `refunded`, etc.).
* Docstrings et exemples d’utilisation enrichis dans le code (endpoints FastAPI en exemples).
* Cohérence des variables d’environnement : `FEDAPAY_API_URL`, `FEDAPAY_API_KEY`, `FEDAPAY_AUTH_KEY`, `FEDAPAY_ENDPOINT_NAME`, `FEDAPAY_DB_URL`.

---

### Corrections

* Correction de plusieurs problèmes liés à la persistance et au rechargement des processus d’écoute (meilleure gestion des erreurs et logs).
* Correction dans la gestion des timeouts et suppression de transactions en cas de statut `pending` lors du timeout interne.
* Nettoyage et robustification des interactions avec les services bas-niveau (`Transactions`, `Balances`, `Webhooks`, etc.).

---

### Modifications fichier-par-fichier (changements saillants)

* **`connector.py`**
  * Amélioration du cœur du connecteur (`FedapayConnector`) et correction de bugs mineurs.
  * Ajout / renforcement du cycle de vie des callbacks : `set_on_persited_listening_processes_loading_finished_callback`, `set_payment_callback_function`, `set_webhook_callback_function`.
  * Ajout des méthodes clés : `fedapay_save_webhook_data`, `fedapay_pay`, `fedapay_finalise`, `fedapay_cancel_transaction`, `load_persisted_listening_processes`, `shutdown_cleanup`, `fedapay_get_transaction_data(_by_merchant_id)`, etc.

* **`models.py`**
  * Ajout de nouvelles classes Pydantic et amélioration des modèles existants : réponses API plus riches et plus structurées.

* **`integration.py`**
  * Nouveau module `Integration` : façade riche pour les opérations sur Transactions, Balances, Currencies, Events, Logs et Webhooks via les services internes.
  * Exposition de méthodes asynchrones pour CRUD et opérations détaillées (ex. `get_all_transactions`, `create_transaction`, `set_payment_method`, `get_all_balances`, `get_all_webhooks`, etc.).

---

### Migration / Checklist pour passage 1.3.5 → 2.0.0

1. **Vérifier les imports** : ajuster tous les imports déplacés / renommés (ex. `from fedapay_connector.models import ...`, `from fedapay_connector.integrations import Transactions`).
2. **Vérifier les réponses publiques** : adapter le code consommateur pour accéder aux champs restructurés (les anciennes données restent disponibles mais sont désormais mieux structurées).
3. **Adapter le code client** : remplacer les anciens enums / noms (ex. `MethodesPaiement` / `Pays`) par les nouveaux (`TypesPaiement`, `PaiementSetup`, etc.) et gérer le nouveau statut `CANCELLED_INTERNALLY`.
4. **Endpoints webhooks** : si vous utilisez votre propre endpoint, appelez `fedapay_save_webhook_data(event)` après vérification de signature (`utils.verify_signature(...)`), comme montré dans les docstrings.
5. **Tester les callbacks** : vérifier `payment_callback` et `webhooks_callback` ; tester `shutdown_cleanup()` pour garantir un arrêt propre.
6. **Tests** : exécuter la suite de tests (pytest-asyncio) et valider les flows critiques (création transaction, finalisation, timeout, suppression).

---

### Notes additionnelles

* Cette v2.0.0 conserve l’esprit asynchrone et la persistance automatique de la série 1.x, mais **introduit une architecture plus modulaire** pensée pour les intégrations avancées et la robustesse en production.
* Les développeurs souhaitant un contrôle total peuvent utiliser uniquement `Integration` (plutôt que d’instancier `FedapayConnector`) pour interagir avec FedaPay et recevoir des données déjà validées et typées.

---

## Version 1.3.5 (2025-08-07)

* Mise à jour des énumérations : mise à jour des énumérations des types de transaction possibles et des états finaux de transaction acceptés (ajustements des valeurs et des états pris en charge).

## Version 1.3.4 (2025-07-27)

* Statut expired ajouté : ajout du statut "expired" à l'énumération des statuts de transaction (TransactionStatus), pour prendre en compte les paiements expirés.

## Version 1.3.3 (2025-07-23)

* Flag d'annulation interne : ajout d'un indicateur permettant de détecter les annulations internes d'événements dans les flux de paiement.

## Version 1.3.2 (2025-07-20)

* tetative d'ajout de doc automatique au package

## Version 1.3.1 (2025-07-20)

* Persistance en base : ajout d'une persistance automatique des processus métier en base de données et amélioration de la gestion des webhooks.
* Refactorisation : refonte de la structure du code pour retirer les sections redondantes et améliorer la maintenabilité.

## Version 1.2.3 (2025-05-22)

* Corrections de documentation : corrections mineures dans la documentation pour améliorer la clarté du texte.

## Version 1.2.2 (2025-05-22)

* Correction de statut de transaction : résolution d'un problème de gestion des statuts de transaction (correction d'orthographe et alignement du type sur l'énumération TransactionStatus).

## Version 1.2.1 (2025-05-08)

* Documentation et journalisation : amélioration de la description du projet (README) et de la gestion des logs pour une meilleure traçabilité des opération.

## Version 1.2.0 (2025-05-07)

* Nouveaux types de paiements : refonte de la gestion des paiements pour ajouter la prise en charge de nouveaux moyens de paiement.
* Refactorisation des paiements : refactorisation générale du code de gestion des paiements pour améliorer la clarté et la fiabilité.

## Version 1.1.1 (2025-05-04)

* Mise à jour des dépendances : ajustement du fichier requirements.txt, en particulier mise à jour de la dépendance h11 à la version 0.16.0 pour assurer la compatibilit.

## Version 1.1.0 (2025-05-04)

* Restructuration du code : mise à jour de la version en 1.1.0 avec une restructuration importante du code source pour améliorer sa lisibilité et sa maintenabilit.

## Version 1.0.0 (2025-04-20)

* Publication initiale : première version du connecteur asynchrone Fedapay-Connector. Elle introduit les fonctionnalités de base pour interagir avec l'API FedaPay (utilisation d’asyncio, gestion des webhooks, journalisation des événements).
* Types et utilitaires : ajout de définitions de types et de fonctions utilitaires pour faciliter le traitement des paiements.
* Documentation mise à jour : amélioration du README et des méthodes du connecteur pour prendre en charge la gestion des webhooks et la vérification du statut des transactions.
* Refactorisation : restructuration de l'arborescence du projet et des fichiers de configuration pour améliorer la fonctionnalité générale et la gestion des erreurs.