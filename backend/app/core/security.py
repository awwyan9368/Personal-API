import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence
import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db

bearer_scheme = HTTPBearer(auto_error=False)

SUPPORTED_SCOPES = [
    "read:all",
    "write:all",
    "read:habits",
    "write:habits",
    "read:finance",
    "write:finance",
    "read:screen_time",
    "write:screen_time",
    "read:activities",
    "write:activities",
    "read:goals",
    "write:goals",
    "read:journal",
    "write:journal",
    "read:wellbeing",
    "write:wellbeing",
    "read:analytics",
    "read:exports",
    "write:imports",
]


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def generate_api_token() -> tuple[str, str, str]:
    """
    Returns (raw_token, token_prefix, token_hash).
    Raw token is shown only once upon creation.
    """
    random_part = secrets.token_urlsafe(32)
    raw_token = f"plos_{random_part}"
    prefix = raw_token[:12]
    token_hash = hash_api_token(raw_token)
    return raw_token, prefix, token_hash


def hash_api_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_access_token(
    subject: str,
    scopes: Optional[List[str]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload: Dict[str, Any] = {
        "sub": subject,
        "scopes": scopes or ["read:all", "write:all"],
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "session",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials.",
        )


class AuthContext:
    def __init__(
        self,
        user_id: str,
        scopes: List[str],
        auth_type: str = "session",
        token_id: Optional[str] = None,
    ):
        self.user_id = user_id
        self.scopes = scopes
        self.auth_type = auth_type
        self.token_id = token_id

    def has_scope(self, required_scope: str) -> bool:
        if "write:all" in self.scopes:
            return True
        if required_scope.startswith("read:") and "read:all" in self.scopes:
            return True
        if required_scope in self.scopes:
            return True
        # If write:<domain> is granted, also allow read:<domain>
        if required_scope.startswith("read:"):
            domain = required_scope.split(":", 1)[1]
            if f"write:{domain}" in self.scopes:
                return True
        return False


def get_auth_context(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthContext:
    from app.models.entities import ApiToken, UserProfile

    raw_token: Optional[str] = None
    if credentials and credentials.credentials:
        raw_token = credentials.credentials.strip()
    elif "plos_session" in request.cookies:
        raw_token = request.cookies.get("plos_session")
    elif request.headers.get("X-API-Key"):
        raw_token = request.headers.get("X-API-Key", "").strip()

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a Bearer token, X-API-Key header, or active session.",
        )

    # Check if this is a personal API token (prefixed with plos_)
    if raw_token.startswith("plos_"):
        token_hash = hash_api_token(raw_token)
        stmt = select(ApiToken).where(ApiToken.token_hash == token_hash)
        api_token = db.execute(stmt).scalar_one_or_none()
        if not api_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API token.",
            )
        if api_token.is_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This API token has been revoked.",
            )
        now_utc = datetime.now(timezone.utc)
        if api_token.expires_at:
            exp = api_token.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < now_utc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="This API token has expired.",
                )

        # Update last_used_at timestamp
        api_token.last_used_at = now_utc
        db.commit()

        scopes = [s.strip() for s in (api_token.scopes or "").split(",") if s.strip()]
        return AuthContext(
            user_id=api_token.user_id,
            scopes=scopes,
            auth_type="api_token",
            token_id=api_token.id,
        )

    # Otherwise decode as JWT session token
    payload = decode_access_token(raw_token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session payload.",
        )

    user = db.execute(select(UserProfile).where(UserProfile.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User profile not found.",
        )

    scopes = payload.get("scopes", ["read:all", "write:all"])
    return AuthContext(user_id=user.id, scopes=scopes, auth_type="session")


def require_scopes(*required_scopes: str):
    """Dependency factory enforcing one or more permission scopes on an endpoint."""
    def _dependency(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
        for scope in required_scopes:
            if not auth.has_scope(scope):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required scope: '{scope}'. Granted scopes: {auth.scopes}",
                )
        return auth

    return _dependency

