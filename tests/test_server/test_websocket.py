import pytest

from app.server.websocket import ConnectionManager


class FakeWebSocket:
    def __init__(self):
        self.accepted = False
        self.messages = []

    async def accept(self):
        self.accepted = True

    async def send_text(self, message):
        self.messages.append(message)


@pytest.mark.asyncio
async def test_connect_replays_events_broadcast_before_websocket_connected():
    manager = ConnectionManager()
    await manager.broadcast("task-1", {
        "type": "node_status",
        "node_id": "n1",
        "data": {"status": "running"},
    })
    websocket = FakeWebSocket()

    await manager.connect("task-1", websocket)

    assert websocket.accepted is True
    assert websocket.messages == [
        '{"type": "node_status", "node_id": "n1", "data": {"status": "running"}}'
    ]


def test_demucs_runtime_dependency_includes_torchcodec():
    import tomllib
    from pathlib import Path

    data = tomllib.loads(Path("pyproject.toml").read_text())

    assert "torchcodec" in {dependency.split(">=")[0] for dependency in data["project"]["dependencies"]}
