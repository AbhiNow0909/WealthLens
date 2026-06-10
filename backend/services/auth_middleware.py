import os
import httpx
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> dict:
    """
    Validate the Supabase JWT by calling Supabase Auth directly.
    Works for both RS256 (new projects) and HS256 (old projects).
    """
    token = credentials.credentials
    supabase_url = os.environ["SUPABASE_URL"]
    api_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{supabase_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": api_key,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session — please log in again",
        )

    user = resp.json()
    return {"id": user["id"], "email": user.get("email")}
