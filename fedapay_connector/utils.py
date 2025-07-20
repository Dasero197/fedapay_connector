import inspect
import os, logging, hmac, hashlib, time  # noqa: E401
from typing import Callable, Dict, Optional
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
    log_dir = "logs"
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
    callback: Callable, expected_params: Dict[str, type], name: str
) -> None:
    """
    Valide un callback avec plusieurs paramètres.

    Args:
        callback: La fonction de callback à valider
        expected_params: Dictionnaire des paramètres attendus {nom: type}
        name: Nom du callback pour les messages d'erreur
    """
    return
    if not callback:
        raise ValueError(f"{name} callback cannot be None")

    if not callable(callback):
        raise TypeError(f"{name} must be callable")

    if not inspect.iscoroutinefunction(callback):
        raise TypeError(f"{name} must be an async function")

    sig = inspect.signature(callback)
    params = sig.parameters

    # Vérifie que tous les paramètres attendus sont présents avec les bons types
    for param_name, expected_type in expected_params.items():
        if param_name not in params:
            raise TypeError(f"{name} is missing required parameter '{param_name}'")

        param = params[param_name]
        if param.annotation == inspect.Parameter.empty:
            raise TypeError(
                f"Parameter '{param_name}' in {name} must have type annotation"
            )

        if param.annotation != expected_type:
            raise TypeError(
                f"Parameter '{param_name}' in {name} must be of type {expected_type.__name__}, "
                f"got {param.annotation.__name__}"
            )

    # Vérifie qu'il n'y a pas de paramètres supplémentaires
    unexpected_params = set(params.keys()) - set(expected_params.keys())
    if unexpected_params:
        raise TypeError(
            f"{name} has unexpected parameters: {', '.join(unexpected_params)}"
        )
