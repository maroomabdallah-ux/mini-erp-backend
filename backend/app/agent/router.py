from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import func

from app.agent import repository
from app.agent.assistant import ask_agent
from app.agent.models import ChatConversation, ChatMessage
from app.agent.schemas import (
    AgentChatRequest,
    AgentChatResponse,
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
)
from app.core.dependencies import CurrentUser, DatabaseSession

router = APIRouter(
    prefix="/agent",
    tags=["AI Agent"],
)


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
    history: list[dict[str, str]] = []
    if request.conversation_id is not None:
        conversation = repository.get_conversation(
            db, request.conversation_id, current_user.id
        )
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        history = [
            {"role": item.role, "content": item.content}
            for item in conversation.messages[-20:]
        ]

    try:
        answer = ask_agent(user=current_user, message=message, history=history)

        if conversation is None:
            title = " ".join(message.split())[:120]
            conversation = ChatConversation(user_id=current_user.id, title=title)
            db.add(conversation)
            db.flush()

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

        return AgentChatResponse(
            answer=answer,
            conversation_id=conversation.id,
        )

    except RuntimeError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="AI assistant is temporarily unavailable.",
        ) from exc


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
