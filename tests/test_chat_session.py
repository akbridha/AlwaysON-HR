"""Tests for multi-turn chat session history."""
from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from src.agent import AgentService
from src.cache import NullCache
from src.config import Settings
from src.contracts import AuthContext, ChatRequest, ModelTurn
from src.retrieval import RetrievalService
from src.repository import MemoryRepository
from src.tools import ToolExecutor


ALYA = {"Authorization": "Bearer token-alya"}
BIMA = {"Authorization": "Bearer token-bima"}


def test_second_message_receives_prior_context(
    client: TestClient,
    repository: MemoryRepository,
) -> None:
    """The second message in the same conversation_id should include prior turns."""
    # First message: ask about leave balance
    resp1 = client.post("/api/v1/chat", headers=ALYA, json={"message": "saldo cuti saya"})
    assert resp1.status_code == 200
    conv_id = resp1.json()["conversation_id"]
    assert conv_id  # must be present and non-empty

    stored = repository.load_conversation(conv_id, "EMP-001", 20)
    assert stored == [
        {"role": "user", "content": "saldo cuti saya"},
        {"role": "assistant", "content": "Saldo cuti Anda tersedia sesuai catatan HR."},
    ]

    # Second message in the same conversation
    resp2 = client.post(
        "/api/v1/chat",
        headers=ALYA,
        json={"message": "ulangi pertanyaan sebelumnya", "conversation_id": conv_id},
    )
    assert resp2.status_code == 200
    # conversation_id must be preserved
    assert resp2.json()["conversation_id"] == conv_id


def test_different_conversation_id_starts_fresh(
    client: TestClient,
    repository: MemoryRepository,
) -> None:
    """Two different conversation_ids are independent sessions."""
    resp_a = client.post("/api/v1/chat", headers=ALYA, json={"message": "saldo cuti saya"})
    assert resp_a.status_code == 200
    conv_a = resp_a.json()["conversation_id"]

    resp_b = client.post("/api/v1/chat", headers=ALYA, json={"message": "saldo cuti saya"})
    assert resp_b.status_code == 200
    conv_b = resp_b.json()["conversation_id"]

    # Each request without a conversation_id gets its own new id
    assert conv_a != conv_b
    assert repository.load_conversation(conv_b, "EMP-001", 20)
    assert repository.load_conversation("CV-NEVER-USED", "EMP-001", 20) == []


def test_conversation_history_is_employee_scoped(
    client: TestClient,
    repository: MemoryRepository,
) -> None:
    """Alya's conversation_id cannot be used by Bima to read Alya's history."""
    # Alya starts a conversation
    resp = client.post("/api/v1/chat", headers=ALYA, json={"message": "saldo cuti saya"})
    assert resp.status_code == 200
    conv_id = resp.json()["conversation_id"]

    # Bima sends a message using Alya's conversation_id — should start fresh (no history)
    # The agent should not see Alya's turns; it must succeed but with an empty prior history
    resp_bima = client.post(
        "/api/v1/chat",
        headers=BIMA,
        json={"message": "ulangi pertanyaan sebelumnya", "conversation_id": conv_id},
    )
    assert resp_bima.status_code == 200
    # Bima gets a valid response (the conversation starts empty for them, no cross-employee leak)
    assert resp_bima.json()["answer"]
    assert repository.load_conversation(conv_id, "EMP-002", 20) == [
        {"role": "user", "content": "ulangi pertanyaan sebelumnya"},
        {
            "role": "assistant",
            "content": "Belum ada percakapan sebelumnya yang dapat dirangkum.",
        },
    ]
    alya_history = repository.load_conversation(conv_id, "EMP-001", 20)
    assert all(turn["content"] != "ulangi pertanyaan sebelumnya" for turn in alya_history)


class HistoryCapturingProvider:
    def __init__(self) -> None:
        self.calls: list[list[dict]] = []

    def embed(self, texts):
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs):
        input_data = kwargs["input_data"]
        self.calls.append(input_data)
        return ModelTurn(
            response_id="history-check",
            text="Jawaban yang menggunakan riwayat percakapan.",
            input_tokens=10,
            output_tokens=10,
        )


def test_agent_passes_loaded_history_to_provider(repository: MemoryRepository) -> None:
    provider = HistoryCapturingProvider()
    settings = Settings(model_mode="fake")
    retrieval = RetrievalService(repository, provider, NullCache(), 0)
    tools = ToolExecutor(repository, retrieval, settings, today_factory=lambda: date(2026, 9, 23))
    agent = AgentService(repository, provider, tools, settings)
    auth = AuthContext(employee_id="EMP-001", display_name="Alya Pratama")

    first = agent.run(ChatRequest(message="Apa pertanyaan saya sebelumnya?"), auth)
    second = agent.run(
        ChatRequest(
            message="Rangkum pertanyaan dan jawaban sebelumnya.",
            conversation_id=first.conversation_id,
        ),
        auth,
    )

    assert second.conversation_id == first.conversation_id
    assert len(provider.calls) == 2
    second_turn_input = provider.calls[1]
    assert {"role": "user", "content": "Apa pertanyaan saya sebelumnya?"} in second_turn_input
    assert {
        "role": "assistant",
        "content": "Jawaban yang menggunakan riwayat percakapan.",
    } in second_turn_input


def test_third_turn_can_summarize_prior_context(client: TestClient) -> None:
    first = client.post(
        "/api/v1/chat",
        headers=ALYA,
        json={"message": "Berapa jatah cuti tahunan?"},
    )
    assert first.status_code == 200
    conv_id = first.json()["conversation_id"]

    second = client.post(
        "/api/v1/chat",
        headers=ALYA,
        json={"message": "Berapa saldo cuti saya?", "conversation_id": conv_id},
    )
    assert second.status_code == 200

    third = client.post(
        "/api/v1/chat",
        headers=ALYA,
        json={"message": "Rangkum pertanyaan dan jawaban sebelumnya.", "conversation_id": conv_id},
    )
    assert third.status_code == 200
    answer = third.json()["answer"]
    assert "Ringkasan percakapan sebelumnya" in answer
    assert "Berapa jatah cuti tahunan?" in answer
    assert "Berapa saldo cuti saya?" in answer
