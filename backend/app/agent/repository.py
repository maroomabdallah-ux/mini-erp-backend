from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agent.models import AgentPendingAction, ChatConversation


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
    return cast(
        ChatConversation | None,
        db.scalar(
            select(ChatConversation)
            .options(selectinload(ChatConversation.messages))
            .where(
                ChatConversation.id == conversation_id,
                ChatConversation.user_id == user_id,
            )
        )
    )


def get_pending_action_for_update(
    db: Session, action_id: int, user_id: int
) -> AgentPendingAction | None:
    return cast(
        AgentPendingAction | None,
        db.scalar(
            select(AgentPendingAction)
            .where(
                AgentPendingAction.id == action_id,
                AgentPendingAction.user_id == user_id,
            )
            .with_for_update()
        ),
    )


def list_pending_actions_for_update(
    db: Session, *, user_id: int, conversation_id: int, action_type: str
) -> list[AgentPendingAction]:
    return list(
        db.scalars(
            select(AgentPendingAction)
            .where(
                AgentPendingAction.user_id == user_id,
                AgentPendingAction.conversation_id == conversation_id,
                AgentPendingAction.action_type == action_type,
                AgentPendingAction.status == "pending",
            )
            .with_for_update()
        ).all()
    )


def get_latest_pending_action(
    db: Session, *, user_id: int, conversation_id: int
) -> AgentPendingAction | None:
    return cast(
        AgentPendingAction | None,
        db.scalar(
            select(AgentPendingAction)
            .where(
                AgentPendingAction.user_id == user_id,
                AgentPendingAction.conversation_id == conversation_id,
                AgentPendingAction.status == "pending",
            )
            .order_by(AgentPendingAction.created_at.desc(), AgentPendingAction.id.desc())
            .limit(1)
        ),
    )
