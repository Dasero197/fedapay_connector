class FedapayError(Exception):
    """Erreur générique Fedapay"""


class InvalidCountryPaymentCombination(FedapayError):
    """Combinaison pays methode de paiement invalide"""


class EventError(FedapayError):
    """Erreur d'événement"""


class ConfigError(FedapayError):
    """Erreur de configuration de la classe principale"""


class FedapayServerError(FedapayError):
    """Status code innatendue pour une requete fedapay (plus de 400)"""


class TransactionIsNotPendingAnymore(FedapayError):
    """Levée si une transaction n'est plus en attente et qu'on tente de l'annuler"""