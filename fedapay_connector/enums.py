from enum import Enum

class Pays(str, Enum):
    benin = "bj"
    cote_d_ivoire = "ci"
    niger = "ne"
    senegal = "sn"
    togo = "tg"
    guinee = "gn"

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
