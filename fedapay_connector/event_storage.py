from contextlib import contextmanager
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from typing import Optional
import logging
from pydantic import BaseModel
from .db_models import Base, StoredListeningProcess
import os


class ProcessPersistance:
    def __init__(
        self,
        logger: logging.Logger,
        db_url: Optional[
            str
        ] = "sqlite:///fedapay_connector_persisted_data/processes.db",
    ):
        os.makedirs("fedapay_connector_persisted_data", exist_ok=True)
        self.engine = create_engine(db_url)
        self.session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        self.logger = logger
        self._init_db()

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
