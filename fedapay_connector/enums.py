from enum import Enum


class Pays(str, Enum):
    benin = "bj"
    cote_d_ivoire = "ci"
    niger = "ne"
    senegal = "sn"
    togo = "tg"
    guinee = "gn"
    mali = "ml"
    burkina_faso = "bf"


class Monnaies(str, Enum):
    xof = "XOF"
    gnf = "GNF"


class MethodesPaiement(str, Enum):
    mtn_open = "MTN Mobile Money Bénin"
    moov = "Moov Bénin"
    sbin = "Celtis Bénin"
    mtn_ci = "MTN Mobile Money Côte d'Ivoire"
    moov_tg = "Moov Togo"
    togocel = "Togocel T-Money"
    free_sn = "Free Sénégal"
    airtel_ne = "Airtel Niger"
    mtn_open_gn = "MTN Mobile Money Guinée"


class TransactionStatus(str, Enum):
    created = "created"
    refunded = "refunded"
    transferred = "transferred"
    pending = "pending"
    approved = "approved"
    canceled = "canceled"
    declined = "declined"
    expired = "expired"


class EventFutureStatus(str, Enum):
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RESOLVED = "resolved"
    CANCELLED_INTERNALLY = "cancelled_internally"


class TypesPaiement(str, Enum):
    AVEC_REDIRECTION = "avec_redirection"
    SANS_REDIRECTION = "sans_redirection"


class ExceptionOnProcessReloadBehavior(str, Enum):
    DROP_AND_REMOVE_PERSISTANCE = "drop_and_remove_persistence"
    DROP_AND_KEEP_PERSISTED = "drop_and_keep_persisted"
    KEEP_AND_RETRY = "keep_and_retry"
