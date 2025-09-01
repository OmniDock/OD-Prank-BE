from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from typing import Optional
from app.core.config import settings
from uuid import UUID

security = HTTPBearer()

class AuthUser:
    """Represents an authenticated user from Supabase"""
    def __init__(self, user_id: str, email: str = None, metadata: dict = None):
        try:
            self.id = UUID(user_id) if isinstance(user_id, str) else user_id
            self.id_str = str(self.id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user ID format in token"
            )
        self.email = email
        self.metadata = metadata or {}
    
    def __str__(self):
        return f"AuthUser(id={self.id}, email={self.email})"

async def verify_jwt_token(token: str) -> dict:
    """Verify JWT token with Supabase"""
    try:
        payload = jwt.decode(
            token, 
            settings.SUPABASE_JWT_SECRET, 
            algorithms=["HS256"],
            audience="authenticated"
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> AuthUser:
    """Extract and validate user from JWT token - Required authentication"""
    token = credentials.credentials
    payload = await verify_jwt_token(token)
    
    # Extract user info from JWT payload
    user_id = payload.get("sub")
    email = payload.get("email")
    user_metadata = payload.get("user_metadata", {})
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user ID"
        )
    
    return AuthUser(user_id=user_id, email=email, metadata=user_metadata)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[AuthUser]:
    """Optional user dependency - returns None if no token provided"""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
