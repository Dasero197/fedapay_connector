from .enums import Pays, MethodesPaiement, Monnaies

Paiement_Map = {
    Pays.benin: {
        MethodesPaiement.mtn_open,
        MethodesPaiement.moov,
        MethodesPaiement.sbin
    },
    Pays.cote_d_ivoire: {
        MethodesPaiement.mtn_ci,
    },
    Pays.niger: {
        MethodesPaiement.airtel_ne
    },
    Pays.senegal: {
        MethodesPaiement.free_sn
    },
    Pays.togo: {
        MethodesPaiement.moov_tg,
        MethodesPaiement.togocel
    },
    Pays.guinee: {
        MethodesPaiement.mtn_open_gn
    },
}


Monnaies_Map = {
    Pays.guinee: Monnaies.gnf,
    Pays.benin: Monnaies.xof,
    Pays.cote_d_ivoire: Monnaies.xof,
    Pays.niger: Monnaies.xof,
    Pays.senegal: Monnaies.xof,
    Pays.togo: Monnaies.xof,
}

