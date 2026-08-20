"""Authentication guard tests: 401 on missing/invalid keys, 200 on success,
403 on cross-project access."""


async def test_missing_key_401(client):
    resp = await client.get("/v1/projects/1")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


async def test_invalid_key_401(client):
    resp = await client.get(
        "/v1/projects/1", headers={"Authorization": "Bearer tfsk_doesnotexist"}
    )
    assert resp.status_code == 401


async def test_auth_success(client, create_project):
    project_id, key = await create_project(name="auth-ok")
    resp = await client.get(
        f"/v1/projects/{project_id}", headers={"Authorization": f"Bearer {key}"}
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "auth-ok"


async def test_cross_project_403(client, create_project):
    pid_a, key_a = await create_project(name="a")
    pid_b, _ = await create_project(name="b")
    resp = await client.get(
        f"/v1/projects/{pid_b}", headers={"Authorization": f"Bearer {key_a}"}
    )
    assert resp.status_code == 403