"""API endpoint tests (FastAPI httpx client + SQLite)."""


async def test_health(client) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "environment" in body


async def test_department_crud(client) -> None:
    r = await client.post("/departments", json={"name": "Research Dept"})
    assert r.status_code == 201
    dept = r.json()

    r = await client.get("/departments")
    assert r.status_code == 200
    assert any(d["id"] == dept["id"] for d in r.json())

    r = await client.get(f"/departments/{dept['id']}")
    assert r.status_code == 200

    r = await client.patch(f"/departments/{dept['id']}", json={"description": "Updated"})
    assert r.status_code == 200
    assert r.json()["description"] == "Updated"


async def test_agent_crud(client) -> None:
    r = await client.post("/departments", json={"name": "Automation Dept"})
    dept = r.json()

    r = await client.post(
        "/agents",
        json={"name": "COO", "role": "coo", "department_id": dept["id"],
              "permissions": ["task.create", "task.assign"]},
    )
    assert r.status_code == 201
    agent = r.json()

    r = await client.get("/agents")
    assert r.status_code == 200
    assert any(a["id"] == agent["id"] for a in r.json())

    r = await client.get(f"/agents/{agent['id']}")
    assert r.status_code == 200


async def test_task_lifecycle(client) -> None:
    r = await client.post("/tasks", json={"title": "Task A"})
    assert r.status_code == 201
    task = r.json()
    assert task["status"] == "PENDING"

    r = await client.get(f"/tasks/{task['id']}")
    assert r.status_code == 200

    # assign with no actor (system) succeeds
    r = await client.post(f"/tasks/{task['id']}/assign", json={"assignee_agent_id": "x"})
    assert r.status_code in (200, 404)  # assignee may not exist -> 404

    # valid transition
    r = await client.post(f"/tasks/{task['id']}/transition", json={"target_status": "QUEUED"})
    assert r.status_code == 200
    assert r.json()["status"] == "QUEUED"

    # invalid transition
    r = await client.post(f"/tasks/{task['id']}/transition", json={"target_status": "REVIEW"})
    assert r.status_code == 409
    assert r.json()["type"] == "InvalidStateTransitionError"

    # history
    r = await client.get(f"/tasks/{task['id']}/history")
    assert r.status_code == 200
    assert [h["new_status"] for h in r.json()] == ["PENDING", "QUEUED"]


async def test_objective_create_and_run(client) -> None:
    r = await client.post("/objectives", json={"title": "Increase TrendEra affiliate revenue"})
    assert r.status_code == 201
    objective = r.json()
    assert objective["status"] == "PENDING"

    r = await client.get(f"/objectives/{objective['id']}")
    assert r.status_code == 200

    r = await client.post(f"/objectives/{objective['id']}/run")
    assert r.status_code == 200
    body = r.json()
    assert body["workflow"]["ok"] is True
    assert body["objective"]["status"] == "COMPLETED"


async def test_audit_logs_filtering(client) -> None:
    r = await client.get("/audit-logs")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    r = await client.get("/audit-logs", params={"action": "nonexistent.action"})
    assert r.status_code == 200
    assert r.json() == []


async def test_openapi_available(client) -> None:
    r = await client.get("/openapi.json")
    assert r.status_code == 200
    assert "paths" in r.json()

    r = await client.get("/docs")
    assert r.status_code == 200