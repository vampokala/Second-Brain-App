"""Async and sync SQLAlchemy engines and session factories."""

from __future__ import annotations

from functools import lru_cache
from typing import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from src.utils.sb_env import load_second_brain_settings


@lru_cache
def get_async_engine():
    s = load_second_brain_settings()
    return create_async_engine(
        s.database_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )


def async_session_factory():
    return async_sessionmaker(get_async_engine(), expire_on_commit=False)


@lru_cache
def get_sync_engine():
    s = load_second_brain_settings()
    return create_engine(
        s.database_url_sync,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )


def sync_session_factory():
    return sessionmaker(get_sync_engine(), expire_on_commit=False, class_=Session)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    factory = async_session_factory()
    async with factory() as session:
        yield session
