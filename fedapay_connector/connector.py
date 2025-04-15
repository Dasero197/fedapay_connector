from fedapay_connector.schemas import PaiementSetup, UserData, PaymentHistory, WebhookHistory
from fedapay_connector.maps import Monnaies_Map
from fedapay_connector.enums import Pays
from fedapay_connector.utils import initialize_logger 
from datetime import datetime, timedelta, timezone
from typing import Optional, Callable, Awaitable
import os, asyncio, aiohttp  # noqa: E401



#Type des callbacks utilisées par l'utilisateur pour historiser les operations lui même
OperationCallback = Callable[[PaymentHistory], Awaitable[None]]
WebhookCallback = Callable[[WebhookHistory], Awaitable[None]]

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


    
    def _get_currency(self, pays:Pays):
        """
        Fonction interne pour obtenir la devise du pays.

        Args:
            pays (pays): Enum représentant le pays.

        Returns:
            str: Code ISO de la devise du pays.
        """
        return Monnaies_Map.get(pays).value
  
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
                    "currency" : {"iso" : self._get_currency(setup.pays)},
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

    def save_webhook_data(self, id_transaction: int, statut_transaction: str, reference: str, commision: float, fees: int, receipt_url: str, function_callback: Optional[WebhookCallback] = None):
        """
        Enregistre les données du webhook pour une transaction donnée.

        Args:
            id_transaction (int): ID de la transaction.
            statut_transaction (str): Statut de la transaction.
            reference (str): Référence externe de la transaction.
            commision (float): Commission prélevée par FedaPay.
            fees (int): Frais associés à la transaction.
            receipt_url (str): Lien vers le reçu de la transaction.
            function_callback (Optional[WebhookCallback]): Fonction de rappel pour traiter les données du webhook.
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
    
    async def Check_Fedapay_status(self, id_transaction:int,api_key:Optional[str]= os.getenv("API_KEY")):
        """
        Vérifie le statut d'une transaction FedaPay.

        Args:
            id_transaction (int): ID de la transaction.
            api_key (Optional[str]): Clé API pour l'authentification.

        Returns:
            dict: Statut, frais et commission de la transaction.

        Example:
            status = await paiement_fedapay_class.Check_Fedapay_status(12345)
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
