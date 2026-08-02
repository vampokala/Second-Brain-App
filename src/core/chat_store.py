"""Persistent chat storage (Postgres + FTS + branching)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.models import Chat, Message, MessageCitation


@dataclass
class NewMessage:
    role: str
    content: str
    parent_id: uuid.UUID | None = None
    retrieved: list[dict[str, Any]] | None = None


@dataclass
class MessageHit:
    message_id: uuid.UUID
    chat_id: uuid.UUID
    role: str
    content_preview: str
    rank: float


@dataclass
class ChatWithMessages:
    chat: Chat
    messages: list[Message]
    citations_by_message: dict[uuid.UUID, list[MessageCitation]]


class ChatStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._factory

    async def create_chat(
        self,
        *,
        title: str | None,
        system_prompt: str | None,
        provider: str,
        model: str,
        scope: str,
    ) -> Chat:
        ch = Chat(
            title=title,
            system_prompt=system_prompt,
            provider=provider,
            model=model,
            knowledge_scope=scope,
        )
        async with self._factory() as session:
            session.add(ch)
            await session.commit()
            await session.refresh(ch)
            return ch

    async def list_chats(self, limit: int = 50) -> list[Chat]:
        stmt: Select = (
            select(Chat).order_by(Chat.pinned.desc(), Chat.updated_at.desc()).limit(limit)
        )
        async with self._factory() as session:
            res = await session.execute(stmt)
            return list(res.scalars().unique().all())

    async def _branch_message_ids(self, session: AsyncSession, leaf_id: uuid.UUID) -> list[uuid.UUID]:
        q = text(
            """
            WITH RECURSIVE branch AS (
                SELECT id, parent_id, created_at FROM messages WHERE id = :leaf
                UNION ALL
                SELECT m.id, m.parent_id, m.created_at
                FROM messages m
                JOIN branch b ON m.id = b.parent_id
            )
            SELECT id FROM branch ORDER BY created_at ASC
            """
        )
        res = await session.execute(q, {"leaf": leaf_id})
        return [row[0] for row in res.all()]

    async def _default_leaf(self, session: AsyncSession, chat_id: uuid.UUID) -> uuid.UUID | None:
        row = await session.execute(
            select(Message.id).where(Message.chat_id == chat_id).order_by(Message.created_at.desc()).limit(1)
        )
        return row.scalar_one_or_none()

    async def get_chat(self, chat_id: uuid.UUID) -> ChatWithMessages | None:
        async with self._factory() as session:
            ch = await session.get(Chat, chat_id)
            if ch is None:
                return None
            leaf = ch.active_leaf_id or await self._default_leaf(session, chat_id)
            if leaf is None:
                return ChatWithMessages(chat=ch, messages=[], citations_by_message={})
            ids = await self._branch_message_ids(session, leaf)
            if not ids:
                return ChatWithMessages(chat=ch, messages=[], citations_by_message={})
            res = await session.execute(select(Message).where(Message.id.in_(ids)).order_by(Message.created_at.asc()))
            msgs = list(res.scalars().unique().all())
            cit_res = await session.execute(
                select(MessageCitation).where(MessageCitation.message_id.in_([m.id for m in msgs]))
            )
            cites = list(cit_res.scalars().all())
            by_m: dict[uuid.UUID, list[MessageCitation]] = {}
            for c in cites:
                by_m.setdefault(c.message_id, []).append(c)
            return ChatWithMessages(chat=ch, messages=msgs, citations_by_message=by_m)

    async def _set_search_vector(self, session: AsyncSession, message_id: uuid.UUID, content: str) -> None:
        await session.execute(
           text(
                "UPDATE messages SET search_vector = to_tsvector('english', :c) WHERE id = :id"
            ),
            {"c": content, "id": message_id},
        )

    async def append_message(self, chat_id: uuid.UUID, msg: NewMessage) -> Message:
        m = Message(
            chat_id=chat_id,
            role=msg.role,
            content=msg.content,
            parent_id=msg.parent_id,
            retrieved=msg.retrieved,
        )
        async with self._factory() as session:
            session.add(m)
            await session.flush()
            await self._set_search_vector(session, m.id, m.content)
            await session.execute(
                update(Chat).where(Chat.id == chat_id).values(updated_at=func.now(), active_leaf_id=m.id)
            )
            await session.commit()
            await session.refresh(m)
            return m

    async def add_citations(
        self,
        message_id: uuid.UUID,
        citations: Sequence[tuple[str, str, str | None, float | None]],
    ) -> None:
        async with self._factory() as session:
            for chunk_id, source, title, score in citations:
                session.add(
                    MessageCitation(
                        message_id=message_id,
                        chunk_id=chunk_id,
                        source=source,
                        title=title,
                        score=score,
                    )
                )
            await session.commit()

    async def update_chat(self, chat_id: uuid.UUID, **fields: Any) -> Chat | None:
        allowed = {
            "title",
            "pinned",
            "system_prompt",
            "provider",
            "model",
            "knowledge_scope",
            "summary_cache",
            "active_leaf_id",
        }
        data = {k: v for k, v in fields.items() if k in allowed}
        if not data:
            async with self._factory() as session:
                return await session.get(Chat, chat_id)
        async with self._factory() as session:
            await session.execute(update(Chat).where(Chat.id == chat_id).values(**data, updated_at=func.now()))
            await session.commit()
            return await session.get(Chat, chat_id)

    async def delete_message(self, message_id: uuid.UUID) -> None:
        async with self._factory() as session:
            await session.execute(delete(MessageCitation).where(MessageCitation.message_id == message_id))
            await session.execute(delete(Message).where(Message.id == message_id))
            await session.commit()

    async def delete_chat(self, chat_id: uuid.UUID) -> None:
        async with self._factory() as session:
            await session.execute(delete(Chat).where(Chat.id == chat_id))
            await session.commit()

    async def search(self, q: str, limit: int = 50) -> list[MessageHit]:
        q = (q or "").strip()
        if not q:
            return []
        async with self._factory() as session:
            stmt = text(
                """
                SELECT id, chat_id, role,
                       LEFT(content, 400) AS preview,
                       ts_rank(search_vector, plainto_tsquery('english', :q)) AS rank
                FROM messages
                WHERE search_vector @@ plainto_tsquery('english', :q)
                ORDER BY rank DESC
                LIMIT :lim
                """
            )
            res = await session.execute(stmt, {"q": q, "lim": limit})
            hits: list[MessageHit] = []
            for mid, cid, role, preview, rank in res.all():
                hits.append(
                    MessageHit(
                        message_id=mid,
                        chat_id=cid,
                        role=role,
                        content_preview=str(preview or ""),
                        rank=float(rank or 0.0),
                    )
                )
            return hits

    async def fork_at(self, chat_id: uuid.UUID, message_id: uuid.UUID) -> uuid.UUID:
        async with self._factory() as session:
            old = await session.get(Chat, chat_id)
            if old is None:
                raise ValueError("chat not found")
            anchor = await session.get(Message, message_id)
            if anchor is None or anchor.chat_id != chat_id:
                raise ValueError("message not in chat")
            ids = await self._branch_message_ids(session, message_id)
            res = await session.execute(select(Message).where(Message.id.in_(ids)).order_by(Message.created_at.asc()))
            old_msgs = list(res.scalars().unique().all())
            new_chat = Chat(
                title=old.title,
                system_prompt=old.system_prompt,
                provider=old.provider,
                model=old.model,
                knowledge_scope=old.knowledge_scope,
                pinned=False,
            )
            session.add(new_chat)
            await session.flush()
            id_map: dict[uuid.UUID, uuid.UUID] = {}
            last_new: Message | None = None
            for om in old_msgs:
                new_parent = id_map.get(om.parent_id) if om.parent_id else None
                nm = Message(
                    chat_id=new_chat.id,
                    role=om.role,
                    content=om.content,
                    parent_id=new_parent,
                    provider=om.provider,
                    model=om.model,
                    elapsed_ms=om.elapsed_ms,
                    feedback=om.feedback,
                )
                session.add(nm)
                await session.flush()
                id_map[om.id] = nm.id
                await self._set_search_vector(session, nm.id, nm.content)
                last_new = nm
            if last_new:
                new_chat.active_leaf_id = last_new.id
            await session.commit()
            return new_chat.id

    async def set_leaf(self, chat_id: uuid.UUID, message_id: uuid.UUID | None) -> None:
        async with self._factory() as session:
            await session.execute(
                update(Chat).where(Chat.id == chat_id).values(active_leaf_id=message_id, updated_at=func.now())
            )
            await session.commit()

    async def get_message(self, message_id: uuid.UUID) -> Message | None:
        async with self._factory() as session:
            return await session.get(Message, message_id)
