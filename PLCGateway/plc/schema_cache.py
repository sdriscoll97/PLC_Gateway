"""Thread-safe RAM + disk cache for normalized Logix controller schemas.

The gateway owns structural discovery. Workstation clients never need PLC
addresses and repeated tree expansion must not rediscover controller types.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

CACHE_FORMAT = 1


def _utcnow():
    return datetime.now(timezone.utc).isoformat()


class SchemaCache:
    def __init__(self, cache_dir=None):
        configured = cache_dir or os.environ.get("PLC_GATEWAY_SCHEMA_CACHE")
        self.cache_dir = Path(configured or "schema-cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory = {}
        self._locks = {}
        self._guard = threading.RLock()
        self.discovery_counts = {}

    def _lock_for(self, plc):
        with self._guard:
            return self._locks.setdefault(plc, threading.RLock())

    def _path(self, plc):
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in plc)
        return self.cache_dir / (safe + ".schema.json")

    def _load_disk(self, plc):
        path = self._path(plc)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("format") != CACHE_FORMAT or data.get("plc") != plc:
                return None
            if not isinstance(data.get("roots"), list) or not isinstance(data.get("types"), dict):
                return None
            return data
        except (OSError, ValueError, TypeError):
            return None

    def _write_disk(self, plc, data):
        path = self._path(plc)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, path)

    def _next_generation(self, plc):
        current = self._memory.get(plc) or self._load_disk(plc)
        return int((current or {}).get("generation", 0)) + 1

    def get(self, plc, discover, refresh=False):
        """Return normalized schema, discovering exactly once on a cache miss.

        ``discover`` must return ``(roots, types)``. A per-PLC lock prevents
        concurrent clients from causing duplicate controller discoveries.
        """
        lock = self._lock_for(plc)
        with lock:
            if not refresh:
                cached = self._memory.get(plc)
                if cached is not None:
                    return cached, "memory"
                cached = self._load_disk(plc)
                if cached is not None:
                    self._memory[plc] = cached
                    return cached, "disk"

            roots, types = discover()
            generation = self._next_generation(plc)
            data = {
                "format": CACHE_FORMAT,
                "plc": plc,
                "generation": generation,
                "created_at": _utcnow(),
                "roots": roots,
                "types": types,
            }
            self._write_disk(plc, data)
            self._memory[plc] = data
            self.discovery_counts[plc] = self.discovery_counts.get(plc, 0) + 1
            return data, "discovery"

    def status(self, plc):
        with self._lock_for(plc):
            data = self._memory.get(plc)
            source = "memory"
            if data is None:
                data = self._load_disk(plc)
                source = "disk" if data is not None else "none"
            if data is None:
                return {
                    "plc": plc, "cached": False, "source": "none",
                    "generation": 0, "root_count": 0, "type_count": 0,
                    "created_at": None,
                    "process_discovery_count": self.discovery_counts.get(plc, 0),
                }
            return {
                "plc": plc, "cached": True, "source": source,
                "generation": int(data.get("generation", 0)),
                "root_count": len(data.get("roots", [])),
                "type_count": len(data.get("types", {})),
                "created_at": data.get("created_at"),
                "process_discovery_count": self.discovery_counts.get(plc, 0),
            }

    def invalidate(self, plc):
        with self._lock_for(plc):
            self._memory.pop(plc, None)
            try:
                self._path(plc).unlink()
            except FileNotFoundError:
                pass
