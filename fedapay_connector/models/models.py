from typing import Any, Optional, List, Dict
from datetime import datetime
from pydantic import Field, model_validator, EmailStr
from ..maps import Paiement_Map
from ..enums import Pays, MethodesPaiement, TypesPaiement, TransactionStatus
from ..exceptions import InvalidCountryPaymentCombination
import json
from .base import Base


class ListMeta(Base):
    """
    Modèle pour l'objet 'meta' contenant les informations de pagination.
    """

    current_page: int
    next_page: Optional[int] = None
    prev_page: Optional[int] = None
    per_page: int
    total_pages: int
    total_count: int


class Metadata(Base):
    expire_schedule_jobid: Optional[str] = None


class Customer(Base):
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


class Currency(Base):
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


class AssetUrls(Base):
    original: Optional[str] = None
    thumbnail: Optional[str] = None


class AssetMetadata(Base):
    filename: Optional[str] = None
    size: Optional[int] = None
    mime_type: Optional[str] = None


class Asset(Base):
    klass: Optional[str] = None
    id: Optional[int] = None
    public: Optional[bool] = None
    mime_type: Optional[str] = None
    urls: Optional[AssetUrls] = None
    original_metadata: Optional[AssetMetadata] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserAccount(Base):
    klass: Optional[str] = None
    id: Optional[int] = None
    account_id: Optional[int] = None
    user_id: Optional[int] = None
    role_id: Optional[int] = None


class User(Base):
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


class ApiKey(Base):
    klass: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    public_key: Optional[str] = None


class Balance(Base):
    klass: Optional[str] = None
    id: Optional[int] = None
    amount: Optional[float] = None
    mode: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Account(Base):
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


class Transaction(Base):
    klass: Optional[str] = None
    id: Optional[int] = None
    reference: Optional[str] = None
    amount: Optional[float] = None
    description: Optional[str] = None
    callback_url: Optional[str] = None
    status: TransactionStatus
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


class TransactionListResponse(Base):
    transactions: List[Transaction] = Field(
        ..., alias="v1/transactions", description="La liste des transactions."
    )
    meta: ListMeta


class WebhookTransaction(Base):
    name: Optional[str] = None
    object: Optional[str] = None
    entity: Optional[Transaction] = None
    account: Optional[Account] = None


class TransactionPaymentMethodResponse(Base):
    reference: Optional[str] = Field(
        ...,
        description="Référence unique de l'opération de paiement (souvent le numéro de la transaction FedaPay).",
    )
    status: TransactionStatus = Field(
        ...,
        description="Statut de la demande de paiement (e.g., pending, approved, declined).",
    )


class TransactionDeleteStatus(Base):
    delete_status: bool
    status_code: int
    message: Optional[str] = None


class TransactionToken(Base):
    token: Optional[str] = None
    payment_link: Optional[str] = Field(
        ...,
        alias="url",
    )


class UserData(Base):
    nom: str
    prenom: str
    email: EmailStr
    tel: str


class PaiementSetup(Base):
    pays: Pays
    method: Optional[MethodesPaiement] = None
    type_paiement: Optional[TypesPaiement] = TypesPaiement.SANS_REDIRECTION

    @model_validator(mode="after")
    def check_valid_combination(self):
        Pays = self.pays
        method = self.method
        type_paiement = self.type_paiement

        if type_paiement == TypesPaiement.SANS_REDIRECTION:
            # Vérification de la méthode de paiement pour les pays avec paiement sans redirection
            if Pays not in Paiement_Map.keys():
                raise InvalidCountryPaymentCombination(
                    f"Le pays [{Pays}] ne supporte pas le paiement sans redirection"
                )

            # Vérification de la méthode de paiement pour les pays avec paiement sans redirection
            if method is None:
                raise InvalidCountryPaymentCombination(
                    "La méthode de paiement est requise pour le paiement sans redirection"
                )

            # méthodes supportées
            if method not in Paiement_Map.get(Pays, set()):
                raise InvalidCountryPaymentCombination(
                    f"Méthode de paiement [{method}] non supportée pour le pays [{Pays}]"
                )

        elif type_paiement == TypesPaiement.AVEC_REDIRECTION:
            if method is not None:
                print(
                    "[warning] La méthode de paiement est ignorée pour le paiement avec redirection"
                )
            self.method = None

        return self


class ListeningProcessData(Base):
    id_transaction: int
    received_webhooks: Optional[list[WebhookTransaction]] = None


class PaidCustomerMetadata(Base):
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    email: Optional[EmailStr] = None


class TransactionMetadata(Base):
    expire_schedule_jobid: Optional[str] = None
    paid_customer: Optional[PaidCustomerMetadata] = None
    transfer_schedule_jobid: Optional[str] = None


class EventEntityResponse(Base):
    id: int
    status: str
    reference: str
    amount: int
    operation: str
    mode: Optional[str] = None

    # Dates
    created_at: str
    updated_at: str
    approved_at: Optional[str] = None
    transferred_at: Optional[str] = None
    expired_at: Optional[str] = None

    # Montants et frais
    fees: Optional[int] = None
    commission: Optional[str] = None  # Souvent une chaîne de pourcentage
    amount_transferred: Optional[int] = None
    amount_debited: Optional[int] = None

    # Références et IDs
    account_id: int
    currency_id: int
    customer_id: Optional[int] = None
    balance_id: Optional[int] = None
    payment_method_id: Optional[int] = None

    # Champs spécifiques aux événements de Transfert
    transferred_count: Optional[int] = None
    to_be_transferred_at: Optional[str] = None

    # Métadonnées
    metadata: Optional[TransactionMetadata] = None
    custom_metadata: Optional[Dict[str, Any]] = None

    # URL
    callback_url: Optional[str] = None
    receipt_url: Optional[str] = None

    # Champs techniques/spécifiques
    last_error_code: Optional[str] = None
    last_error_message: Optional[str] = None


class EventResponse(Base):
    """
    Modèle pour un objet d'événement unique.
    (Élément de la liste v1/events)
    """

    id: str
    klass: str = Field(..., description="Le type de classe FedaPay (e.g., v1/event).")
    type: str = Field(
        ..., description="Le nom de l'événement (e.g., transaction.approved)."
    )

    # IMPORTANT: 'entity' est reçu comme une chaîne JSON.
    # Le type 'str' doit être utilisé ici pour la réception brute.
    entity: str = Field(
        ...,
        description="La chaîne JSON représentant l'objet déclencheur (e.g., Transaction).",
    )

    object_id: int
    account_id: int
    object: str = Field(
        ..., description="Le type d'objet déclencheur (e.g., transaction)."
    )

    created_at: str
    updated_at: str

    def get_parsed_entity(self) -> EventEntityResponse:
        """
        Méthode utilitaire pour décoder le champ 'entity' et le valider avec le modèle Pydantic.
        """
        try:
            entity_dict = json.loads(self.entity)
            return EventEntityResponse(**entity_dict)
        except json.JSONDecodeError as e:
            raise ValueError(f"Erreur de décodage JSON de l'entité de l'événement: {e}")
        except Exception as e:
            raise ValueError(f"Erreur de validation Pydantic de l'entité: {e}")


class EventListResponse(Base):
    events: List[EventResponse] = Field(
        ..., alias="v1/events", description="La liste des events."
    )
    meta: ListMeta


class BalanceResponse(Base):
    """
    Modèle pour un solde unique (Balance) du compte marchand,
    tel qu'il apparaît dans la liste 'v1/balances'.
    """

    klass: str = Field(..., description="Le type de classe FedaPay (e.g., v1/balance).")
    id: int
    amount: int = Field(
        ..., description="Le montant total du solde (en unités de la devise)."
    )
    mode: Optional[str] = Field(
        None,
        description="Le mode de paiement associé à ce solde (e.g., 'moov', 'stripe_gw', 'bank_transfer').",
    )
    created_at: str
    updated_at: str


class BalanceListResponse(Base):
    balances: List[BalanceResponse] = Field(
        ..., alias="v1/balances", description="La liste des balances."
    )
    meta: Optional[ListMeta] = None


class LogCurrency(Base):
    """Devise utilisée dans la requête."""

    iso: str = Field(..., description="Code ISO 4217 de la devise (e.g., XOF).")


class LogPhoneNumber(Base):
    """Numéro de téléphone du client dans la requête."""

    number: str
    country: str = Field(..., description="Code pays ISO 3166-1 alpha-2 (e.g., ci).")


class LogCustomer(Base):
    """Informations du client dans la requête."""

    firstname: Optional[str] = None
    lastname: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: LogPhoneNumber


class LogTransactionRequest(Base):
    """Contenu de la clé 'transaction' dans le body de la requête."""

    description: str
    callback_url: str
    amount: int


class LogRequestBody(Base):
    """
    Modèle pour le contenu décodé du champ 'body' du log (création de transaction).
    """

    description: str
    amount: int
    currency: LogCurrency
    callback_url: str
    customer: LogCustomer
    transaction: LogTransactionRequest


class LogTransactionResponse(Base):
    """
    Modèle pour le contenu décodé du champ 'response' du log (Transaction créée).
    """

    id: int
    reference: str
    description: str
    amount: int
    status: str
    created_at: str
    updated_at: str

    # Références et IDs
    currency_id: int
    customer_id: Optional[int] = None
    account_id: int

    # Optionnels et Métadonnées
    callback_url: Optional[str] = None
    mode: Optional[str] = None
    approved_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class LogResponse(Base):
    klass: str = Field(..., description="Le type de classe FedaPay (e.g., v1/log).")
    id: str
    method: str = Field(..., description="Méthode HTTP (e.g., GET, POST).")
    url: str = Field(..., description="Endpoint appelé (e.g., /v1/transactions).")
    status: int = Field(..., description="Code de statut HTTP (e.g., 200).")
    ip_address: str
    version: str
    source: str

    # Les champs chaînes JSON
    query: str = Field(..., description="Chaîne JSON des paramètres de requête.")
    body: str = Field(..., description="Chaîne JSON du corps de la requête.")
    response: str = Field(..., description="Chaîne JSON de la réponse de l'API.")

    account_id: int
    created_at: str
    updated_at: str

    def get_decoded_body(self) -> LogRequestBody:
        """Décode et valide la chaîne JSON du 'body'."""
        return LogRequestBody(**json.loads(self.body))

    def get_decoded_response(self) -> LogTransactionResponse:
        """Décode et valide la chaîne JSON de la 'response'."""
        # Note: La réponse n'est pas encapsulée ici, elle est l'objet transaction directement.
        return LogTransactionResponse(**json.loads(self.response))


class LogListResponse(Base):
    logs: List[LogResponse] = Field(
        ..., alias="v1/logs", description="La liste des logs."
    )
    meta: ListMeta


class CurrencyResponse(Base):
    """
    Modèle pour un objet devise unique (Currency) de l'API FedaPay.
    """

    klass: str = Field(
        ..., description="Le type de classe FedaPay (e.g., v1/currency)."
    )
    id: int
    name: str = Field(..., description="Nom de la devise (e.g., FCFA).")
    iso: str = Field(..., description="Code ISO 4217 (e.g., XOF).")
    code: int
    prefix: Optional[str] = Field(
        None, description="Préfixe du symbole monétaire (peut être null)."
    )
    suffix: Optional[str] = Field(
        None, description="Suffixe du symbole monétaire (e.g., CFA)."
    )
    div: int = Field(
        ...,
        description="Diviseur pour convertir en unités de base (généralement 1 ou 100).",
    )
    default: bool = Field(
        ..., description="Indique si c'est la devise par défaut du compte."
    )

    # Modes de paiement
    modes: List[str] = Field(
        ..., description="Liste des modes de paiement supportés par cette devise."
    )

    # Horodatage
    created_at: str
    updated_at: str


class CurrencyListResponse(Base):
    currencies: List[CurrencyResponse] = Field(
        ..., alias="v1/currencies", description="La liste des currencies."
    )
    meta: Optional[ListMeta] = None


class WebhookResponse(Base):
    """
    Modèle pour un objet webhook unique de l'API FedaPay.
    """

    klass: str = Field(..., description="Le type de classe FedaPay (e.g., v1/webhook).")
    id: int
    url: str = Field(..., description="L'URL où les notifications sont envoyées.")
    enabled: bool = Field(..., description="Indique si le webhook est actif.")
    ssl_verify: bool = Field(
        ..., description="Indique si la vérification SSL est activée pour l'URL."
    )
    disable_on_error: bool = Field(
        ...,
        description="Indique si le webhook doit être désactivé après des erreurs consécutives.",
    )
    account_id: int

    # Champ structurel
    http_headers: Dict[str, str] = Field(
        ...,
        description="Les en-têtes HTTP personnalisés à envoyer avec les requêtes de webhook.",
    )

    # Horodatage
    created_at: str
    updated_at: str


class WebhookListResponse(Base):
    # La liste des objets Webhook, encapsulée sous la clé 'v1/webhooks'
    webhooks: List[WebhookResponse] = Field(
        ..., alias="v1/webhooks", description="La liste des webhooks configurés."
    )

    # Les métadonnées d'API
    meta: ListMeta


class FedapayPay(Base):
    transaction_data: Transaction
    link_and_token_data: TransactionToken
    set_methode_data: Optional[TransactionPaymentMethodResponse]
    status: TransactionStatus


class PaymentHistory(FedapayPay):
    pass


class WebhookHistory(WebhookTransaction):
    pass
