from fastapi.testclient import TestClient
from sqlalchemy import select

import app.db.models
from app.core.dependencies import get_current_user
from app.db.session import SessionLocal
from app.features.users.model import User
from app.main import app


def test_agent_chat_endpoint(monkeypatch):

    # Get a real ERP user from the database
    with SessionLocal() as db:
        user = db.scalar(
            select(User).where(
                User.username == "sales"
            )
        )

        assert user is not None

        # Keep the user attached for the test
        db.expunge(user)

    # Override authentication for this test only
    def fake_current_user():
        return user

    app.dependency_overrides[get_current_user] = fake_current_user

    # Fake the Agent so NO OpenAI request happens
    def fake_ask_agent(user, message, conversation_id, history=None):
        return f"Fake agent response for: {message}"

    monkeypatch.setattr(
        "app.agent.router.ask_agent",
        fake_ask_agent,
    )

    client = TestClient(app)

    response = client.post(
        "/agent/chat",
        json={
            "message": "Show me the available products"
        },
    )

    assert response.status_code == 200

    body = response.json()
    assert body["answer"] == "Fake agent response for: Show me the available products"
    assert isinstance(body["conversation_id"], int)

    history_response = client.get("/agent/conversations")
    assert history_response.status_code == 200
    assert any(item["id"] == body["conversation_id"] for item in history_response.json())

    conversation_response = client.get(
        f"/agent/conversations/{body['conversation_id']}"
    )
    assert conversation_response.status_code == 200
    assert [message["role"] for message in conversation_response.json()["messages"]] == [
        "user",
        "assistant",
    ]

    delete_response = client.delete(
        f"/agent/conversations/{body['conversation_id']}"
    )
    assert delete_response.status_code == 204

    # Clean dependency override
    app.dependency_overrides.clear()
