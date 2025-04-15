class FedapayError(Exception):
    """Erreur générique Fedapay"""

class TransactionTimeout(FedapayError):
    """La transaction a expiré sans webhook"""

class InvalidCountryPaymentCombination(FedapayError):
    """Combinaison pays methode de paiement invalide"""