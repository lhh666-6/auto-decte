from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.modules.tasks.models import TaskCommand
from app.services.container import build_services
from config.settings import Settings


def test_task_events_resume_after_last_event_id(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path))
    task = services.tasks.submit(
        TaskCommand("FORM_RECOGNITION", "FORM-1", "operator-1", "key-1", {})
    )
    services.tasks.start(task.task_id)
    services.tasks.report(task.task_id, 50, "recognizing")
    client = TestClient(create_app(services))

    response = client.get(
        f"/api/v1/tasks/{task.task_id}/events",
        headers={"X-Roles": "OPERATOR", "Last-Event-ID": "2"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "id: 3" in response.text
