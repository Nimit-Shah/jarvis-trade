"""Regression tests: chat messages accept arbitrarily long research briefs.

The Web UI's ``POST /sessions/{id}/messages`` used to cap ``content`` at 5000
characters (``SendMessageRequest``), returning FastAPI 422 for every large
research prompt (e.g. a ~10k-char systematic-framework brief) while the CLI,
MCP, and the scheduled-research API accepted the same text without limit. The
cap was removed entirely — these tests pin that contract.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api_server


class _CapturingSessionService:
    """Minimal SessionService double: records content, spawns nothing."""

    def __init__(self) -> None:
        self.received: list[str] = []

    async def send_message(self, session_id: str, content: str, include_shell_tools: bool = False):
        self.received.append(content)
        return {"message_id": "msg-length-test", "attempt_id": "attempt-length-test"}


def _client(monkeypatch: pytest.MonkeyPatch, service: _CapturingSessionService) -> TestClient:
    monkeypatch.setattr(api_server, "_get_session_service", lambda: service)
    monkeypatch.setenv("API_AUTH_KEY", "secret")
    monkeypatch.setattr(api_server, "_API_KEY", "secret")
    return TestClient(api_server.app, client=("127.0.0.1", 50000))


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer secret"}


def test_send_message_accepts_prompt_longer_than_old_5000_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ~10.5k-char research brief (the shape that used to 422) must be accepted."""
    service = _CapturingSessionService()
    client = _client(monkeypatch, service)
    long_brief = (
        "I want to build a systematic framework for identifying high-momentum "
        "Indian stocks. " * 160
    )  # > 5000 chars
    assert len(long_brief) > 5000

    response = client.post(
        "/sessions/abcdef012345/messages",
        headers=_auth_headers(),
        json={"content": long_brief},
    )

    assert response.status_code == 200, response.text
    assert response.json()["message_id"] == "msg-length-test"
    assert service.received == [long_brief]


def test_send_message_accepts_very_large_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cap was removed entirely — 50k chars flows through untouched."""
    service = _CapturingSessionService()
    client = _client(monkeypatch, service)
    huge_prompt = "Analyze this multi-factor momentum playbook. " * 1000  # ~45k chars
    assert len(huge_prompt) > 40_000

    response = client.post(
        "/sessions/abcdef012345/messages",
        headers=_auth_headers(),
        json={"content": huge_prompt},
    )

    assert response.status_code == 200, response.text
    assert service.received == [huge_prompt]


def test_send_message_still_rejects_empty_content(monkeypatch: pytest.MonkeyPatch) -> None:
    """min_length=1 is preserved: an empty message is still a 422."""
    service = _CapturingSessionService()
    client = _client(monkeypatch, service)

    response = client.post(
        "/sessions/abcdef012345/messages",
        headers=_auth_headers(),
        json={"content": ""},
    )

    assert response.status_code == 422
    assert service.received == []
