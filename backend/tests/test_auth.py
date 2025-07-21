import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_auth_me_unauthorized():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing or invalid Authorization header" 