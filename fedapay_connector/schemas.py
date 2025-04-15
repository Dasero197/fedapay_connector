from pydantic import BaseModel, model_validator,EmailStr
from fedapay_connector.maps import Paiement_Map
from fedapay_connector.enums import Pays, MethodesPaiement
from fedapay_connector.exceptions import InvalidCountryPaymentCombination
from datetime import datetime

class UserData(BaseModel):
    nom: str
    prenom: str
    email: EmailStr
    tel : str

class PaiementSetup(BaseModel):
    pays: Pays
    method: MethodesPaiement

    @model_validator(mode='after')
    def check_valid_combination(self):
        Pays = self.pays
        method = self.method

        # méthodes supportées
        if method not in Paiement_Map.get(Pays, set()):
            raise InvalidCountryPaymentCombination(f"Méthode de paiement [{method}] non supportée pour le pays [{Pays}]")
        return self

class PaymentHistory(BaseModel):
    id_transaction_fedapay: int
    operation: str
    external_customer_id: str
    montant: float
    status: str
    payment_link: str
    external_reference: str

class WebhookHistory(BaseModel):
    id_transaction_fedapay: int
    horodateur: datetime
    fedapay_commission: float
    frais: int
    status: str
    lien_recu: str
    reference: str