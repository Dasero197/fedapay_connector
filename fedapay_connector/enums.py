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
    pending = "pending"
    approved = "approved"
    cancelled = "cancelled"
    declined = "declined"

class EventFutureStatus(str, Enum):
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RESOLVED = "resolved"

class TypesPaiement(str, Enum):
    AVEC_REDIRECTION = "avec_redirection"
    SANS_REDIRECTION = "sans_redirection"
