class FedapayError(Exception):
    """Erreur générique Fedapay"""


class InvalidCountryPaymentCombination(FedapayError):
    """Combinaison pays methode de paiement invalide"""


class EventError(FedapayError):
    """Erreur d'événement"""


class ConfigError(FedapayError):
    """Erreur de configuration de la classe principale"""
