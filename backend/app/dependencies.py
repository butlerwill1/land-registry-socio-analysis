from __future__ import annotations

from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from .auth import get_principal
from .data_repository import DataRepository
from .schemas import Principal


def get_repository(request: Request) -> DataRepository:
    return request.app.state.repository


def get_database_session(request: Request) -> Generator[Session, None, None]:
    with Session(request.app.state.engine) as session:
        yield session


def get_current_principal(request: Request) -> Principal:
    return get_principal(request)
