"""
FedaPay Connector

Copyright (C) 2025 ASSOGBA Dayane

Ce programme est un logiciel libre : vous pouvez le redistribuer et/ou le modifier
conformément aux termes de la GNU Affero General Public License publiée par la
Free Software Foundation, soit la version 3 de la licence, soit (à votre choix)
toute version ultérieure.

Ce programme est distribué dans l'espoir qu'il sera utile,
mais SANS AUCUNE GARANTIE ; sans même la garantie implicite de
COMMERCIALISATION ou D'ADÉQUATION À UN OBJECTIF PARTICULIER.
Consultez la GNU Affero General Public License pour plus de détails.

Vous devriez avoir reçu une copie de la GNU Affero General Public License
avec ce programme. Si ce n'est pas le cas, consultez <https://www.gnu.org/licenses/>.
"""

from fedapay_connector.schemas import PaiementSetup, UserData, PaymentHistory, WebhookHistory
from fedapay_connector.utils import initialize_logger, get_currency, aiohttp_with_error_extractor
from fedapay_connector.types import WebhookCallback, OperationCallback
from datetime import datetime, timedelta, timezone
from typing import Optional
import os, asyncio, aiohttp  # noqa: E401

class FedapayConnector():
    """
    Classe principale pour interagir avec l'API FedaPay. 
    Cette classe permet de gérer les transactions, les statuts et les webhooks liés à FedaPay.
    FONCTIONNE UNIQUEMENT DANS UN CONTEXTE ASYNCHRONE
    """
    _instance = None  

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(FedapayConnector, cls).__new__(cls, *args, **kwargs)
        return cls._instance
     
    def __init__(self):
        """
        Initialise la classe _Paiement_Fedapay avec les paramètres nécessaires.
        """
        self.fedapay_url = os.getenv("API_URL")
        self.received_webhook = {}
        self.logger = initialize_logger()

  
    async def _init_transaction(self, setup: PaiementSetup, client_infos: UserData, montant_paiement : int, callback_url : Optional[str]= None, api_key:Optional[str]= os.getenv("API_KEY")):
        """
        Initialise une transaction avec FedaPay.

        Args:
            setup (PaiementSetup): Configuration du paiement.
            client_infos (UserData): Informations du client.
            montant_paiement (int): Montant du paiement.
            callback_url (Optional[str]): URL de rappel pour les notifications.
            api_key (Optional[str]): Clé API pour l'authentification.

        Returns:
            dict: Détails de la transaction initialisée.

        Example:
            setup = PaiementSetup(pays=pays.benin, method=MethodesPaiement.mtn)
            client = UserData(nom="Doe", prenom="John", email="john.doe@example.com", tel="66000001")
            transaction = await paiement_fedapay_class._init_transaction(setup, client, 10000)
        """
        self.logger.info("Initialisation de la transaction avec FedaPay.")
        header = {"Authorization" : f"Bearer {api_key}",
                  "Content-Type": "application/json"}
        
        body = {    "description" : f"Transaction pour {client_infos.prenom} {client_infos.nom}",
                    "amount" : montant_paiement,
                    "currency" : {"iso" : get_currency(setup.pays)},
                    "callback_url" : callback_url,
                    "customer" : {
                        "firstname" : client_infos.prenom,
                        "lastname" : client_infos.nom,
                        "email" : client_infos.email,
                        "phone_number" : {
                            "number" : client_infos.tel,
                            "country" : setup.pays.value.lower()
                        }
                        }
                    }

        async with aiohttp.ClientSession(headers=header,raise_for_status=True) as session:
            async with session.post(f"{self.fedapay_url}/v1/transactions", json= body) as response:
                response.raise_for_status()  
                init_response = await response.json()  

        self.logger.info(f"Transaction initialisée avec succès: {init_response}")
        init_response = init_response.get("v1/transaction")

        return  {
            "external_id" : init_response.get("id"),
            "status" : init_response.get("status"),
            "external_customer_id" : init_response.get("external_customer_id"),
            "operation": init_response.get("operation")
                            }
    
    async def _get_token(self, id_transaction: int, api_key:Optional[str]= os.getenv("API_KEY")):
        """
        Récupère un token pour une transaction donnée.

        Args:
            id_transaction (int): ID de la transaction.
            api_key (Optional[str]): Clé API pour l'authentification.

        Returns:
            dict: Token et lien de paiement associés à la transaction.

        Example:
            token_data = await paiement_fedapay_class._get_token(12345)
        """
        self.logger.info(f"Récupération du token pour la transaction ID: {id_transaction}")
        header = {"Authorization" : f"Bearer {api_key}",
                  "Content-Type": "application/json"}
        
        async with aiohttp.ClientSession(headers=header,raise_for_status=True) as session:
            async with session.post(f"{self.fedapay_url}/v1/transactions/{id_transaction}/token" ) as response:
                response.raise_for_status()  
                data = await response.json()

        self.logger.info(f"Token récupéré avec succès: {data}")
        return {"token":data.get("token"), "payment_link" : data.get("url")} 
    
    async def _set_methode(self, client_infos: UserData, setup: PaiementSetup, token: str, api_key:Optional[str]= os.getenv("API_KEY")):
        """
        Définit la méthode de paiement pour une transaction.

        Args:
            setup (PaiementSetup): Configuration du paiement.
            token (str): Token de la transaction.
            api_key (Optional[str]): Clé API pour l'authentification.

        Returns:
            dict: Référence et statut de la méthode de paiement.

        Example:
            methode_data = await paiement_fedapay_class._set_methode(setup, "token123")
        """
        self.logger.info(f"Définition de la méthode de paiement pour le token: {token}")
        header = {"Authorization" : f"Bearer {api_key}",
                  "Content-Type": "application/json"}
        
        body = {"token" : token,
                "phone_number" : {
                    "number" : client_infos.tel,
                    "country" : setup.pays.value
                } }

        async with aiohttp.ClientSession(headers=header,raise_for_status=True) as session:
            async with session.post(f"{self.fedapay_url}/v1/{setup.method.name}", json = body ) as response:
                response.raise_for_status()  
                data = await response.json()
        
        self.logger.info(f"Méthode de paiement définie avec succès: {data}")
        data = data.get("v1/payment_intent")

        return {"reference":data.get("reference"),
                "status" : data.get("status")}
    
    async def _check_status(self, id_transaction:int, api_key:Optional[str]= os.getenv("API_KEY")):
        """
        Vérifie le statut d'une transaction.

        Args:
            id_transaction (int): ID de la transaction.
            api_key (Optional[str]): Clé API pour l'authentification.

        Returns:
            dict: Statut, frais et commission de la transaction.

        Example:
            status = await paiement_fedapay_class._check_status(12345)
        """
        self.logger.info(f"Vérification du statut de la transaction ID: {id_transaction}")
        header = {"Authorization" : f"Bearer {api_key}",
                  "Content-Type": "application/json"}
        
        
        async with aiohttp.ClientSession(headers=header,raise_for_status=True) as session:
            async with session.get(f"{self.fedapay_url}/v1/transactions/{id_transaction}" ) as response:
                response.raise_for_status()  
                data = await response.json()
        
        self.logger.info(f"Statut de la transaction récupéré: {data}")
        data = data.get("v1/transaction")

        return {"status" : data.get("status"),
                "fedapay_commission": data.get("commission"),
                "frais" : data.get("fees") }
        
    async def _await_external_event(self, id_transaction: int, timeout_return: int):
        self.logger.info(f"Attente d'un événement externe pour la transaction ID: {id_transaction}")
        n = int(timeout_return * 2)
        while n > 0:
            if id_transaction in self.received_webhook.keys():
                return True, self.received_webhook.get(id_transaction), None
            else:
                await asyncio.sleep(0.5)
                n -= 1  
        return False, None, "Timeout, try manual polling"
    
    def _del_transaction(self, id_transaction : int):
        self.logger.info(f"Suppression de la transaction ID: {id_transaction} des webhooks reçus.")
        self.received_webhook.pop(id_transaction)
    
    def _garbage_cleaner(self):
        self.logger.info("Nettoyage des webhooks expirés.")
        for keys in list(self.received_webhook.keys()):
            webhook = self.received_webhook[keys]
            if webhook["horodateur"] + timedelta(minutes= 30) < datetime.now(timezone.utc):
                self.received_webhook.pop(keys)
        self.logger.info("Webhook Garbage Collected")

    async def _garbage_cleaner_loop(self):
        """
        Lancement de la boucle de nettoyage des webhooks expirés.

        Cette méthode exécute périodiquement le nettoyage des webhooks expirés
        toutes les 6 heures (21600 secondes).
        """
        self.logger.info("Lancement de la boucle de nettoyage des webhooks.")
        self.logger.info("Lancement Webhook Garbage collection")
        try:
            self._garbage_cleaner()
            
            await asyncio.sleep(21600)
        except Exception as e:
            self.logger.info(e)

    def Save_webhook_data(self, id_transaction: int, statut_transaction: str, reference: str, commision: float, fees: int, receipt_url: str, function_callback: Optional[WebhookCallback] = None):
        """
        Méthode à utiliser dans un endpoint de l'API configuré pour recevoir les events webhook de Fedapay.
        Enregistre les données du webhook Fedapay pour une transaction donnée.

        Args:
            id_transaction (int): ID de la transaction.
            statut_transaction (str): Statut de la transaction.
            reference (str): Référence externe de la transaction.
            commision (float): Commission prélevée par FedaPay.
            fees (int): Frais associés à la transaction.
            receipt_url (str): Lien vers le reçu de la transaction.
            function_callback (Optional[WebhookCallback]): Fonction de rappel pour traiter de manière personnalisée les données du webhook.

        Example:
            Cas d'un endpoint FastAPI ::

                import hashlib
                import hmac
                import os
                import time
                from fastapi import APIRouter, HTTPException, Request, status
                from fedapay_connector import FedapayConnector as FD
                from enum import Enum

                class Agregateurs(Enum):  # peut être mis dans un fichier différent contenant toutes vos énumérations
                    FEDAPAY = "Fedapay"

                router = APIRouter(prefix="/paiement", tags=["Centre d'imagerie"])  # ajouter le router à app dans votre fichier main.py pour un code plus propre

                fd = FD()

                def verify_signature(payload: bytes, sig_header: str, secret: str):
                    # Extraire le timestamp et la signature depuis le header
                    try:
                        parts = sig_header.split(",")
                        timestamp = int(parts[0].split("=")[1])
                        received_signature = parts[1].split("=")[1]
                    except (IndexError, ValueError):
                        raise HTTPException(status_code=400, detail="Malformed signature header")

                    # Calculer la signature HMAC-SHA256
                    signed_payload = f"{timestamp}.{payload.decode('utf-8')}".encode("utf-8")
                    expected_signature = hmac.new(
                        secret.encode("utf-8"), signed_payload, hashlib.sha256
                    ).hexdigest()

                    # Vérifier si la signature correspond
                    if not hmac.compare_digest(expected_signature, received_signature):
                        raise HTTPException(status_code=400, detail="Signature verification failed")

                    # Vérification du délai (pour éviter les requêtes trop anciennes)
                    if abs(time.time() - timestamp) > 300:  # 5 minutes de tolérance
                        raise HTTPException(status_code=400, detail="Request is too old")

                    return True

                @router.post("/webhooks", status_code=status.HTTP_200_OK)
                async def manage_webhook(request: Request):
                    agregateurs = [agre.value for agre in Agregateurs]
                    header = request.headers
                    agregateur = str(header.get("agregateur"))
                    payload = await request.body()

                    if agregateur not in agregateurs:
                        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aggrégateur non reconnu")

                    elif agregateur == Agregateurs.FEDAPAY.value:
                        try:
                            verify_signature(
                                payload,
                                header.get("x-fedapay-signature"),
                                os.getenv("FEDAPAY_WEBHOOK_KEY_EXT"),  # inclure la clé dans un fichier .env
                            )
                        except HTTPException as e:
                            raise e

                        event = await request.json()
                        entity = event.get("entity")
                        fd.Save_webhook_data(
                            entity.get("id"),
                            event.get("name"),
                            entity.get("reference"),
                            entity.get("commission"),
                            entity.get("fees"),
                            entity.get("receipt_url"),  # une fonction personnalisée peut être passée ici
                        )
                        return {"ok"}
                    else:
                        raise HTTPException(
                            status.HTTP_501_NOT_IMPLEMENTED,
                            f"Gestion de l'agrégateur: {agregateur} non implémentée",
                        )
                        ::
        """

        self.logger.info(f"Enregistrement des données du webhook pour la transaction ID: {id_transaction}")
        result = {
             "status" : statut_transaction,
             "horodateur" : datetime.now(timezone.utc),
             "reference" : reference,
             "fedapay_commission" : commision,
             "frais" : fees,
             "lien_recu" : receipt_url
        }    
        self.received_webhook[id_transaction] = result
        if function_callback:
            self.logger.info(f"Appel de la fonction de rappel avec les données de paiement: {result}")
            asyncio.create_task(function_callback(WebhookHistory(**result, id_transaction_fedapay=id_transaction)))

    async def Fedapay_pay(self, setup: PaiementSetup, client_infos: UserData, montant_paiement: int, api_key: Optional[str] = os.getenv("API_KEY"), callback_url: Optional[str] = None, callback_function: Optional[OperationCallback] = None):
        """
        Effectue un paiement via FedaPay.

        Args:
            setup (PaiementSetup): Configuration du paiement, incluant le pays et la méthode de paiement.
            client_infos (UserData): Informations du client (nom, prénom, email, téléphone).
            montant_paiement (int): Montant du paiement en centimes.
            api_key (Optional[str]): Clé API pour l'authentification (par défaut, récupérée depuis les variables d'environnement).
            callback_url (Optional[str]): URL de rappel pour les notifications de transaction.
            callback_function (Optional[OperationCallback]): Fonction de rappel pour historiser les données de paiement.

        Returns:
            dict: Détails de la transaction, incluant l'ID externe, le lien de paiement, et le statut.
        """
        self.logger.info("Début du processus de paiement via FedaPay.")
        init_data = await self._init_transaction(setup= setup, api_key= api_key, client_infos= client_infos, montant_paiement= montant_paiement,  callback_url= callback_url)
        id_transaction = init_data.get("external_id")
        
        token_data = await self._get_token(id_transaction=id_transaction, api_key=api_key)
        token = token_data.get("token")

        set_methode = await self._set_methode(client_infos= client_infos, setup=setup, token=token, api_key=api_key)

        self.logger.info(f"Paiement effectué avec succès: {init_data}")
        result =  {
            "external_customer_id" : init_data.get("external_customer_id"),
            "operation": init_data.get("operation"),
            "id_transaction_fedapay": id_transaction,
            "payment_link" : token_data.get("payment_link"),
            "external_reference": set_methode.get("reference"),
            "status" : set_methode.get("status")}
        
        if callback_function:
            self.logger.info(f"Appel de la fonction de rappel avec les données de paiement: {result}")
            await callback_function(PaymentHistory(**result, montant= montant_paiement))

        return result
    
    async def Check_transaction_status(self, id_transaction:int,api_key:Optional[str]= os.getenv("API_KEY")):
        """
        Vérifie le statut d'une transaction FedaPay.

        Args:
            id_transaction (int): ID de la transaction.
            api_key (Optional[str]): Clé API pour l'authentification.

        Returns:
            dict: Statut, frais et commission de la transaction.

        Example:
            status = await paiement_fedapay_class.Check_transaction_status(12345)
        """
        self.logger.info(f"Vérification du statut de la transaction ID: {id_transaction}")
        status_data = await self._check_status(api_key= api_key, id_transaction= id_transaction)
        return {
                    "status" : status_data.get("status"),
                    "frais": status_data.get("frais"),
                    "fedapay_commission":status_data.get("fedapay_commission")
                }

    async def Fedapay_finalise(self, id_transaction:int, api_key:Optional[str]= os.getenv("API_KEY")):
        """
        Finalise une transaction FedaPay.

        Args:
            id_transaction (int): ID de la transaction.
            api_key (Optional[str]): Clé API pour l'authentification.

        Returns:
            tuple: Données de la transaction et erreur éventuelle.

        Example:
            final_data, error = await paiement_fedapay_class.Fedapay_finalise(12345)
        """
        self.logger.info(f"Finalisation de la transaction ID: {id_transaction}")
        resp,data,error = await self._await_external_event(id_transaction,600)
        if not resp:
            data = await self._check_status(api_key,id_transaction)
        self._del_transaction(id_transaction)
        self.logger.info(f"Transaction finalisée: {data} | {error}")
        return data,error

    def Garbage_collection(self):
        """
        Nettoie les webhooks expirés.

        Example:
            paiement_fedapay_class.Garbage_collection()
        """
        self.logger.info("Début du processus de collecte des déchets.")
        try:
            self._garbage_cleaner()
        except Exception as e:
            self.logger.info(f" Webhook Garbage collection errror : {e}")
