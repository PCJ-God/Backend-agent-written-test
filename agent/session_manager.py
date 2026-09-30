"""session 管理：多窗口隔离与续聊。"""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Session:
    session_id: str
    user_id: str
    history: List[Dict[str, str]] = field(default_factory=list)
    tool_state: Dict[str, Any] = field(default_factory=dict)

    def append(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})


class SessionManager:
    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}

    def create(self, user_id: str, session_id: Optional[str] = None) -> Session:
        sid = session_id or uuid.uuid4().hex
        session = Session(session_id=sid, user_id=user_id)
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def get_or_create(self, user_id: str, session_id: Optional[str] = None) -> Session:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        return self.create(user_id, session_id)
