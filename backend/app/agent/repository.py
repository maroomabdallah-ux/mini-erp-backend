from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agent.models import ChatConversation


def list_conversations(db: Session, user_id: int) -> list[ChatConversation]:
    return list(
        db.scalars(
            select(ChatConversation)
            .where(ChatConversation.user_id == user_id)
            .order_by(ChatConversation.updated_at.desc(), ChatConversation.id.desc())
        ).all()
    )


def get_conversation(
    db: Session, conversation_id: int, user_id: int
) -> ChatConversation | None:
    return db.scalar(
        select(ChatConversation)
        .options(selectinload(ChatConversation.messages))
        .where(
            ChatConversation.id == conversation_id,
            ChatConversation.user_id == user_id,
        )
    )
