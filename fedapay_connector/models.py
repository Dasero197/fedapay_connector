from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel, model_validator,EmailStr
from .maps import Paiement_Map
from .enums import Pays, MethodesPaiement, TypesPaiement
from .exceptions import InvalidCountryPaymentCombination


class Metadata(BaseModel):
    expire_schedule_jobid: Optional[str] = None

class Customer(BaseModel):
    klass: Optional[str] = None
    id: Optional[int] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    account_id: Optional[int] = None
    phone_number_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

class Currency(BaseModel):
    klass: Optional[str] = None
    id: Optional[int] = None
    name: Optional[str] = None
    iso: Optional[str] = None
    code: Optional[int] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    div: Optional[int] = None
    default: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    modes: Optional[List[str]] = None

class AssetUrls(BaseModel):
    original: Optional[str] = None
    thumbnail: Optional[str] = None

class AssetMetadata(BaseModel):
    filename: Optional[str] = None
    size: Optional[int] = None
    mime_type: Optional[str] = None

class Asset(BaseModel):
    klass: Optional[str] = None
    id: Optional[int] = None
    public: Optional[bool] = None
    mime_type: Optional[str] = None
    urls: Optional[AssetUrls] = None
    original_metadata: Optional[AssetMetadata] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class UserAccount(BaseModel):
    klass: Optional[str] = None
    id: Optional[int] = None
    account_id: Optional[int] = None
    user_id: Optional[int] = None
    role_id: Optional[int] = None

class User(BaseModel):
    klass: Optional[str] = None
    id: Optional[int] = None
    email: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    reset_sent_at: Optional[datetime] = None
    admin: Optional[bool] = None
    admin_role: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    locale: Optional[str] = None
    two_fa_enabled: Optional[bool] = None

class ApiKey(BaseModel):
    klass: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    public_key: Optional[str] = None

class Balance(BaseModel):
    klass: Optional[str] = None
    id: Optional[int] = None
    amount: Optional[float] = None
    mode: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class Account(BaseModel):
    klass: Optional[str] = None
    id: Optional[int] = None
    name: Optional[str] = None
    timezone: Optional[str] = None
    country: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    verified: Optional[bool] = None
    reference: Optional[str] = None
    business_type: Optional[str] = None
    business_identity_type: Optional[str] = None
    business_identity_number: Optional[str] = None
    business_vat_number: Optional[str] = None
    business_registration_number: Optional[str] = None
    business_category: Optional[str] = None
    blocked: Optional[bool] = None
    business_website: Optional[str] = None
    business_address: Optional[str] = None
    business_name: Optional[str] = None
    business_phone: Optional[str] = None
    business_email: Optional[str] = None
    business_owner: Optional[str] = None
    business_company_capital: Optional[str] = None
    business_description: Optional[str] = None
    submitted: Optional[bool] = None
    reject_reason: Optional[str] = None
    has_balance_issue: Optional[bool] = None
    blocked_reason: Optional[str] = None
    last_balance_issue_checked_at: Optional[datetime] = None
    prospect_code: Optional[str] = None
    deal_closer_code: Optional[str] = None
    manager_code: Optional[str] = None
    balance_issue_diff: Optional[int] = None
    business_identity_id: Optional[int] = None
    business_vat_id: Optional[int] = None
    business_registration_id: Optional[int] = None
    business_owner_signature_id: Optional[int] = None
    business_identity: Optional[Asset] = None
    business_vat: Optional[Asset] = None
    business_registration: Optional[Asset] = None
    business_owner_signature: Optional[Asset] = None
    user_accounts: Optional[List[UserAccount]] = None
    users: Optional[List[User]] = None
    api_keys: Optional[List[ApiKey]] = None
    balances: Optional[List[Balance]] = None

class Transaction(BaseModel):
    klass: Optional[str] = None
    id: Optional[int] = None
    reference: Optional[str] = None
    amount: Optional[float] = None
    description: Optional[str] = None
    callback_url: Optional[str] = None
    status: Optional[str] = None
    customer_id: Optional[int] = None
    currency_id: Optional[int] = None
    mode: Optional[str] = None
    operation: Optional[str] = None
    metadata: Optional[Metadata] = None
    commission: Optional[float] = None
    fees: Optional[float] = None
    fixed_commission: Optional[float] = None
    amount_transferred: Optional[float] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    declined_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None
    transferred_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    last_error_code: Optional[str] = None
    custom_metadata: Optional[Dict] = None
    amount_debited: Optional[float] = None
    receipt_url: Optional[str] = None
    payment_method_id: Optional[int] = None
    sub_accounts_commissions: Optional[Dict] = None
    transaction_key: Optional[str] = None
    merchant_reference: Optional[str] = None
    account_id: Optional[int] = None
    balance_id: Optional[int] = None
    customer: Optional[Customer] = None
    currency: Optional[Currency] = None
    payment_method: Optional[Dict] = None
    balance: Optional[Dict] = None
    refunds: Optional[List[Dict]] = None

class WebhookTransaction(BaseModel):
    name: Optional[str] = None
    object: Optional[str] = None
    entity: Optional[Transaction] = None
    account: Optional[Account] = None

class UserData(BaseModel):
    nom: str
    prenom: str
    email: EmailStr
    tel : str

class PaiementSetup(BaseModel):
    pays: Pays
    method: Optional[MethodesPaiement] = None
    type_paiement: Optional[TypesPaiement] = TypesPaiement.SANS_REDIRECTION

    @model_validator(mode='after')
    def check_valid_combination(self):
        Pays = self.pays
        method = self.method
        type_paiement = self.type_paiement

        if type_paiement == TypesPaiement.SANS_REDIRECTION:
            # Vérification de la méthode de paiement pour les pays avec paiement sans redirection
            if Pays not in Paiement_Map.keys():
                raise InvalidCountryPaymentCombination(f"Le pays [{Pays}] ne supporte pas le paiement sans redirection")
            
            # Vérification de la méthode de paiement pour les pays avec paiement sans redirection
            if method is None:
                raise InvalidCountryPaymentCombination("La méthode de paiement est requise pour le paiement sans redirection")
            
            # méthodes supportées
            if method not in Paiement_Map.get(Pays, set()):
                raise InvalidCountryPaymentCombination(f"Méthode de paiement [{method}] non supportée pour le pays [{Pays}]")
            
        elif type_paiement == TypesPaiement.AVEC_REDIRECTION:
            if method is not None:
                print("[warning] La méthode de paiement est ignorée pour le paiement avec redirection")
            self.method = None

        return self


class InitTransaction(BaseModel):
    id_transaction : Optional[int]=None
    status : Optional[str]=None
    external_customer_id : Optional[int]=None
    operation : Optional[str]=None

class GetToken(BaseModel):
    token: Optional[str]=None
    payment_link: Optional[str]=None
    
class FedapayPay(InitTransaction):
    payment_link: Optional[str]=None
    montant: Optional[float]=None
    external_reference: Optional[str]=None

class FedapayStatus(BaseModel):
    status : Optional[str]=None
    fedapay_commission : Optional[float]=None
    frais : Optional[float]=None


class PaymentHistory(FedapayPay):
    pass

class WebhookHistory(WebhookTransaction):
    pass