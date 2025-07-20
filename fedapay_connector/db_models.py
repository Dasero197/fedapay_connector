from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
from sqlalchemy.types import DateTime
from datetime import datetime
from sqlalchemy import func


class Base(DeclarativeBase):
    pass


class StoredListeningProcess(Base):
    __tablename__ = "StoredListeningProcess"

    StoredEventWaitingProcess_id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True
    )
    StoredListeningProcess_transaction_id: Mapped[int] = mapped_column(nullable=False)
    StoredListeningProcess_process_data: Mapped[str] = mapped_column(nullable=True)
    StoredListeningProcess_created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
