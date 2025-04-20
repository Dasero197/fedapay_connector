import os, logging  # noqa: E401
from logging.handlers import TimedRotatingFileHandler
from fedapay_connector.enums import Pays
from fedapay_connector.maps import Monnaies_Map
import aiohttp
import json
from typing import TypeVar, Callable, Awaitable, ParamSpec

def initialize_logger():
        """
        Initialise le logger pour afficher les logs dans la console et les enregistrer dans un fichier journalier.
        Le fichier de log est enregistré dans le dossier `log` avec un fichier journalier."""
        
        # Créer le dossier `log` s'il n'existe pas
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Configurer le logger
        logger = logging.getLogger('fedapay_logger')
        logger.setLevel(logging.DEBUG)

        if logger.hasHandlers():
            return logger

        # Format des logs
        log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Handler pour la console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_format)
        logger.addHandler(console_handler)

        # Handler pour le fichier journalier
        file_handler = TimedRotatingFileHandler(
            filename=os.path.join(log_dir, 'fedapay.log'),
            when='midnight',
            interval=1,
            backupCount=90,  # Conserver les logs des 90 derniers jours
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.suffix = "%Y-%m-%d"
        file_handler.namer = lambda name: name + ".log"
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)

        logger.info("Logger initialisé avec succès.")
        return logger

def get_currency(pays:Pays):
        """
        Fonction interne pour obtenir la devise du pays.

        Args:
            pays (pays): Enum représentant le pays.

        Returns:
            str: Code ISO de la devise du pays.
        """
        return Monnaies_Map.get(pays).value



P = ParamSpec("P")  # Paramètres de la fonction
R = TypeVar("R")    # Type de retour

async def aiohttp_with_error_extractor(
    callable_func: Callable[P, Awaitable[R]],
    *args: P.args,
    **kwargs: P.kwargs
) -> R:
    """
    Exécute une fonction asynchrone utilisant aiohttp et capture les erreurs HTTP
    en extrayant les détails du message d'erreur retourné par le serveur.

    Cette fonction est utile pour centraliser la gestion des erreurs liées aux
    requêtes HTTP, en particulier celles retournant un corps JSON expliquant l'erreur.

    Args:
        callable_func (Callable): Une fonction `async` à exécuter.
        *args: Les arguments positionnels à passer à la fonction.
        **kwargs: Les arguments nommés à passer à la fonction.

    Returns:
        Any: Le résultat retourné par la fonction exécutée.

    Raises:
        RuntimeError: En cas d'erreur HTTP (`aiohttp.ClientResponseError`),
        avec les détails extraits du corps de la réponse (si disponible).
    """
    try:
        return await callable_func(*args, **kwargs)
    except aiohttp.ClientResponseError as e:
        error_body = await e.response.text() if e.response else None
        try:
            error_json = json.loads(error_body) if error_body else {}
        except json.JSONDecodeError:
            error_json = {"raw": error_body}
        raise RuntimeError(f"Erreur HTTP {e.status}: {error_json}") from e

