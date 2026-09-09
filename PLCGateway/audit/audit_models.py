from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

@dataclass
class AuditRecord:
    timestamp_utc: datetime
    user_name: str
    client_host: Optional[str]
    plc_name: str
    plc_address: str
    tag_name: str
    old_value: object
    requested_value: object
    actual_value: object
    write_succeeded: bool
    verified: Optional[bool]
    correlation_id: UUID
    error_detail: Optional[str] = None

    @classmethod
    def now(cls, **kwargs):
        return cls(timestamp_utc=datetime.now(timezone.utc), **kwargs)
