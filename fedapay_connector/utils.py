import inspect
import os, logging, hmac, hashlib, time  # noqa: E401
from typing import Callable, Optional
from fastapi import HTTPException
from logging.handlers import TimedRotatingFileHandler
from .enums import Pays
from .maps import Monnaies_Map


def initialize_logger(
    print_log: Optional[bool] = False, save_log_to_file: Optional[bool] = True
):
    """
    Initialise le logger pour afficher les logs dans la console et les enregistrer dans un fichier journalier.
    Le fichier de log est enregistré dans le dossier `log` avec un fichier journalier."""

    # Créer le dossier `log` s'il n'existe pas
    log_dir = "logs/Fedapay_Connector"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Configurer le logger
    logger = logging.getLogger("fedapay_logger")
    logger.setLevel(logging.DEBUG)

    if logger.hasHandlers():
        return logger

    # Format des logs
    log_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Handler pour la console
    if print_log is True:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(log_format)
        logger.addHandler(console_handler)

    # Handler pour le fichier journalier
    if save_log_to_file is True:
        file_handler = TimedRotatingFileHandler(
            filename=os.path.join(log_dir, "fedapay.log"),
            when="midnight",
            interval=1,
            backupCount=90,  # Conserver les logs des 90 derniers jours
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.suffix = "%Y-%m-%d"
        file_handler.namer = lambda name: name + ".log"
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)

    logger.info("Logger initialisé avec succès.")
    return logger


def get_currency(pays: Pays):
    """
    Fonction interne pour obtenir la devise du pays.

    Args:
        pays (pays): Enum représentant le pays.

    Returns:
        str: Code ISO de la devise du pays.
    """
    return Monnaies_Map.get(pays).value


def verify_signature(payload: bytes, sig_header: str, secret: str):
    # Extraire le timestamp et la signature depuis le header
    try:
        parts = sig_header.split(",")
        timestamp = int(parts[0].split("=")[1])
        received_signature = parts[1].split("=")[1]
    except (IndexError, ValueError):
        raise HTTPException(status_code=400, detail="Malformed signature header")

    # Calculer la signature HMAC-SHA256
    signed_payload = f"{timestamp}.{payload.decode('utf-8')}".encode("utf-8")
    expected_signature = hmac.new(
        secret.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()

    # Vérifier si la signature correspond
    if not hmac.compare_digest(expected_signature, received_signature):
        raise HTTPException(status_code=400, detail="Signature verification failed")

    # Vérification du délai (pour éviter les requêtes trop anciennes)
    if abs(time.time() - timestamp) > 300:  # 5 minutes de tolérance
        raise HTTPException(status_code=400, detail="Request is too old")

    return True


def validate_callback(
    callback: Callable, callback_name: str, must_be_async: Optional[bool] = True
) -> None:
    """
    Valide légèrement un callback.

    Args:
        callback: La fonction de callback à valider
        callback_name: Nom du callback pour les messages d'erreur
        must_be_async : Indique si le callback doit être une fonction asynchrone
    """
    if not callback:
        raise ValueError(f"{callback_name} callback cannot be None")

    if not callable(callback):
        raise TypeError(f"{callback_name} must be callable")

    if must_be_async and not inspect.iscoroutinefunction(callback):
        raise TypeError(f"{callback_name} must be an async function")


def get_auth_header(api_key: Optional[str]):
    """Génère l'en-tête d'authentification."""
    key = api_key if api_key else os.getenv("FEDAPAY_API_KEY")
    if not key:
        raise ValueError(
            "API Key non fournie et non trouvée dans les variables d'environnement."
        )
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
