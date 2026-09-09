from __future__ import annotations
import json, os, threading
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class PLCDefinition:
    name: str
    ip: str
    description: str = ""
    slot: int = 0
    micro800: bool = False
    writable_tag_patterns: tuple[str, ...] = ()

class GatewayConfig:
    def __init__(self, path: str | os.PathLike | None = None):
        self.path = Path(path or os.environ.get("PLC_GATEWAY_CONFIG", Path(__file__).with_name("plc_config.json")))
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.read_only = bool(raw.get("read_only", True))
        self.request_timeout_s = float(raw.get("request_timeout_s", 8.0))
        self.max_batch_tags = int(raw.get("max_batch_tags", 64))
        self.max_concurrent_per_plc = int(raw.get("max_concurrent_per_plc", 1))
        self.bind_host = str(raw.get("bind_host", "127.0.0.1"))
        self.bind_port = int(raw.get("bind_port", 8443))
        self.sql_audit_connection = os.environ.get("PLC_GATEWAY_AUDIT_SQL", "")
        self.require_audit_for_writes = bool(raw.get("require_audit_for_writes", True))
        self.write_authorized_users = tuple(raw.get("write_authorized_users", []))
        self.plcs = {}
        for name, item in raw.get("plcs", {}).items():
            self.plcs[name] = PLCDefinition(
                name=name, ip=item["ip"], description=item.get("description", ""),
                slot=int(item.get("slot", 0)), micro800=bool(item.get("micro800", False)),
                writable_tag_patterns=tuple(item.get("writable_tag_patterns", [])))
        if not self.plcs:
            raise ValueError("No PLC definitions configured")
        self._lock = threading.Lock()

    def plc(self, name: str) -> PLCDefinition:
        try: return self.plcs[name]
        except KeyError: raise KeyError(f"Unknown PLC logical name: {name}")
