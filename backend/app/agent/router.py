import logging

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import func

from app.agent import repository
from app.agent.action_schemas import ActionCancellationResponse, ActionExecutionResponse
from app.agent.actions import cancel_pending_action, confirm_pending_action
from app.agent.assistant import ask_agent
from app.agent.models import ChatConversation, ChatMessage
from app.agent.schemas import (
    AgentChatRequest,
    AgentChatResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
)
from app.core.config import settings
from app.core.dependencies import CurrentUser, DatabaseSession

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/agent",
    tags=["AI Agent"],
)


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post(
    "/chat",
    response_model=AgentChatResponse,
)
def chat_with_agent(
    request: AgentChatRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> AgentChatResponse:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message cannot be empty.")

    conversation = None
    created_conversation = False
    history: list[dict[str, str]] = []
    if request.conversation_id is not None:
        conversation = repository.get_conversation(
            db, request.conversation_id, current_user.id
        )
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        history = [
            {"role": item.role, "content": item.content}
            for item in conversation.messages[-settings.agent_max_history_messages :]
        ]

    try:
        if conversation is None:
            title = " ".join(message.split())[:120]
            conversation = ChatConversation(user_id=current_user.id, title=title)
            db.add(conversation)
            db.commit()
            db.refresh(conversation)
            created_conversation = True

        logger.info(
            "agent_request_started user_id=%s conversation_id=%s",
            current_user.id,
            request.conversation_id,
        )
        answer = ask_agent(
            user=current_user,
            message=message,
            conversation_id=conversation.id,
            history=history,
        )

        db.add_all(
            [
                ChatMessage(
                    conversation_id=conversation.id, role="user", content=message
                ),
                ChatMessage(
                    conversation_id=conversation.id, role="assistant", content=answer
                ),
            ]
        )
        conversation.updated_at = func.now()
        db.commit()
        pending_action = repository.get_latest_pending_action(
            db,
            user_id=current_user.id,
            conversation_id=conversation.id,
        )

        logger.info(
            "agent_request_succeeded user_id=%s conversation_id=%s",
            current_user.id,
            conversation.id,
        )

        return AgentChatResponse(
            answer=answer,
            conversation_id=conversation.id,
            pending_action=(
                {
                    "action_id": pending_action.id,
                    "action_type": pending_action.action_type,
                    "status": pending_action.status,
                    "expires_at": pending_action.expires_at,
                    "summary": pending_action.summary,
                }
                if pending_action is not None
                else None
            ),
        )

    except RuntimeError as exc:
        db.rollback()
        if created_conversation and conversation is not None:
            db.delete(conversation)
            db.commit()
        logger.warning(
            "agent_request_failed user_id=%s conversation_id=%s error_category=%s",
            current_user.id,
            request.conversation_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="AI assistant is temporarily unavailable.",
        ) from exc


@router.post(
    "/actions/{action_id}/confirm",
    response_model=ActionExecutionResponse,
)
def confirm_action(
    action_id: int,
    request: Request,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> dict:
    return confirm_pending_action(
        db,
        action_id=action_id,
        user=current_user,
        ip_address=_ip(request),
    )


@router.post(
    "/actions/{action_id}/cancel",
    response_model=ActionCancellationResponse,
)
def cancel_action(
    action_id: int,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> dict:
    return cancel_pending_action(db, action_id=action_id, user=current_user)


@router.get("/conversations", response_model=list[ConversationSummary])
def get_conversations(
    current_user: CurrentUser,
    db: DatabaseSession,
) -> list[ChatConversation]:
    return repository.list_conversations(db, current_user.id)


@router.post("/conversations", response_model=ConversationDetail, status_code=201)
def create_conversation(
    request: ConversationCreate,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> ChatConversation:
    title = " ".join(request.title.split())
    if not title:
        raise HTTPException(status_code=422, detail="Title cannot be empty.")
    conversation = ChatConversation(user_id=current_user.id, title=title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: int,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> ChatConversation:
    conversation = repository.get_conversation(db, conversation_id, current_user.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conversation


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: int,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> Response:
    conversation = repository.get_conversation(db, conversation_id, current_user.id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    db.delete(conversation)
    db.commit()
    return Response(status_code=204)
