import os, logging  # noqa: E401
from logging.handlers import TimedRotatingFileHandler

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
