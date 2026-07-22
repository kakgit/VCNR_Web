from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets


SESSION_TTL_HOURS = 12


@dataclass
class SessionState:
  token: str
  user_id: str
  name: str
  email: str
  role: str
  status: str
  expires_at: datetime

  def to_user(self) -> dict[str, str]:
    return {
      "id": self.user_id,
      "name": self.name,
      "email": self.email,
      "role": self.role,
      "status": self.status,
    }


_sessions: dict[str, SessionState] = {}


def _utc_now() -> datetime:
  return datetime.now(timezone.utc)


def _cleanup_expired_sessions() -> None:
  now = _utc_now()
  expired_tokens = [token for token, session in _sessions.items() if session.expires_at <= now]
  for token in expired_tokens:
    _sessions.pop(token, None)


def create_session(user: dict[str, object]) -> SessionState:
  _cleanup_expired_sessions()
  token = secrets.token_urlsafe(32)
  session = SessionState(
    token=token,
    user_id=str(user["id"]),
    name=str(user["name"]),
    email=str(user["email"]),
    role=str(user["role"]),
    status=str(user["status"]),
    expires_at=_utc_now() + timedelta(hours=SESSION_TTL_HOURS),
  )
  _sessions[token] = session
  return session


def get_session(token: str) -> SessionState | None:
  _cleanup_expired_sessions()
  session = _sessions.get(token)
  if session is None:
    return None
  if session.expires_at <= _utc_now():
    _sessions.pop(token, None)
    return None
  return session


def revoke_session(token: str) -> None:
  _sessions.pop(token, None)


def revoke_user_sessions(user_id: str) -> None:
  matching_tokens = [token for token, session in _sessions.items() if session.user_id == user_id]
  for token in matching_tokens:
    _sessions.pop(token, None)
