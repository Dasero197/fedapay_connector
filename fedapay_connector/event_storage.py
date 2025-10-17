from contextlib import contextmanager
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from typing import Optional
import logging
from pydantic import BaseModel
from .db_models import Base, StoredListeningProcess
import os
from urllib.parse import urlparse


class ProcessPersistance:
    def __init__(
        self,
        logger: logging.Logger,
        db_url: Optional[
            str
        ] = "sqlite:///fedapay_connector_persisted_data/processes.db",
    ):
        self.logger = logger
        self._ensure_sqlite_path(db_url)
        self.engine = create_engine(db_url)
        self.session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self._init_db()

    def _ensure_sqlite_path(self, db_url: str):
        """
        Détecte si l'URL est de type SQLite et crée le répertoire du fichier DB si nécessaire.
        Le répertoire est créé depuis le répertoire courant (où l'application est lancée)
        lorsque l'URL SQLite est de forme relative (sqlite:///path/to/db.db).
        """
        parsed_url = urlparse(db_url)

        if parsed_url.scheme == "sqlite":
            db_path = parsed_url.path
            if not db_path:
                return

            # Ne pas toucher aux bases en mémoire
            if ":memory:" in db_path:
                return

            # Si l'URL est de la forme sqlite:///relative/path.db (trois slashes),
            # on considère le chemin comme relatif au répertoire courant.
            if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////"):
                rel_path = db_path.lstrip("/")
                db_path_resolved = os.path.join(os.getcwd(), rel_path)
            else:
                # Chemin absolu fourni (sqlite:////absolute/path.db) — on le respecte tel quel.
                db_path_resolved = db_path

            db_dir = os.path.dirname(db_path_resolved)
            if db_dir:
                self.logger.info(f"Création du répertoire de la DB SQLite : {db_dir}")
                os.makedirs(db_dir, exist_ok=True)
                self.logger.info(f"Répertoire créé ou déjà existant : {db_dir}")

    def _init_db(self):
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()

        if StoredListeningProcess.__tablename__ not in tables:
            self.logger.info("Creating database tables...")
            Base.metadata.create_all(self.engine)
            self.logger.info("Database tables created successfully")
        else:
            self.logger.info("Database tables already exist")

    def _get_db(self):
        db = self.session()
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def _get_db_session(self):
        db = next(self._get_db())
        try:
            yield db
        finally:
            db.close()

    def save_process(
        self, transaction_id: int, process_data: Optional[BaseModel] = None
    ):
        """Sauvegarde un processus d'ecoute dans la base"""
        with self._get_db_session() as db:
            process_data_json = process_data.model_dump_json() if process_data else None

            stored_process = StoredListeningProcess(
                StoredListeningProcess_transaction_id=transaction_id,
                StoredListeningProcess_process_data=process_data_json,
            )
            db.add(stored_process)
            db.commit()

    def load_processes(self) -> list[StoredListeningProcess]:
        """Charge tous les processus d'ecoute de la base"""
        processes = []
        with self._get_db_session() as db:
            for process in db.query(StoredListeningProcess).all():
                processes.append(process)
        return processes

    def delete_process(self, transaction_id: int):
        """Supprime un processus d'ecoute"""
        with self._get_db_session() as db:
            count = (
                db.query(StoredListeningProcess)
                .filter(
                    StoredListeningProcess.StoredListeningProcess_transaction_id
                    == transaction_id
                )
                .delete()
            )
            db.commit()
            return count != 0

    def update_process(self, transaction_id: int, process_data: BaseModel):
        """Met à jour un processus d'ecoute"""
        with self._get_db_session() as db:
            process_data_json = process_data.model_dump_json() if process_data else None
            count = (
                db.query(StoredListeningProcess)
                .filter(
                    StoredListeningProcess.StoredListeningProcess_transaction_id
                    == transaction_id
                )
                .update({"StoredListeningProcess_process_data": process_data_json})
            )
            db.commit()
            return count != 0
