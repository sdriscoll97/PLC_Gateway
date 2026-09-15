"""Bounded, serialized PLC access. All controller traffic originates on the gateway host."""
from __future__ import annotations
import socket, threading, time
from pylogix import PLC

class PLCError(RuntimeError): pass

class PylogixWrapper:
    def __init__(self, definition, timeout=5.0):
        self.definition = definition
        self.timeout = timeout
        self._lock = threading.RLock()
        self._comm = None

    def close(self):
        with self._lock:
            if self._comm:
                try: self._comm.Close()
                except Exception: pass
            self._comm = None

    def _connection(self):
        if self._comm is None:
            comm = PLC()
            comm.IPAddress = self.definition.ip
            comm.ProcessorSlot = self.definition.slot
            comm.Micro800 = self.definition.micro800
            try: comm.SocketTimeout = self.timeout
            except Exception: pass
            self._comm = comm
        return self._comm

    def read(self, tags):
        if isinstance(tags, str): tags = [tags]
        with self._lock:
            comm = self._connection()
            result = comm.Read(tags if len(tags) > 1 else tags[0])
            return result if isinstance(result, list) else [result]

    def write(self, tag, value):
        with self._lock:
            return self._connection().Write(tag, value)

    def tag_list(self):
        # Keep this identical to the direct PLC_6 test proven on BBCMWPBMX13.
        with self._lock:
            return self._connection().GetTagList()

    def schema_tags(self):
        """Return pycomm3's read-only normalized tag metadata, including UDT definitions."""
        if self.definition.micro800:
            raise PLCError("UDT schema discovery is only supported for Logix controllers")
        try:
            from pycomm3 import LogixDriver
        except ImportError as exc:
            raise PLCError("Schema discovery requires pycomm3") from exc
        endpoint = f"{self.definition.ip}/{self.definition.slot}"
        with self._lock:
            # init_tags=False prevents an implicit enumeration before we explicitly request it.
            with LogixDriver(endpoint, init_tags=False, init_program_tags=False) as driver:
                tags = driver.get_tag_list(program='*')
                return tags

    def plc_time(self):
        with self._lock:
            return self._connection().GetPLCTime()

    def diagnostics(self):
        started = time.perf_counter()
        try:
            with socket.create_connection((self.definition.ip, 44818), timeout=min(self.timeout, 3.0)):
                latency = round((time.perf_counter() - started) * 1000, 2)
        except OSError as exc:
            return {"reachable": False, "tcp_port": 44818, "latency_ms": None, "error": str(exc)}
        result = {"reachable": True, "tcp_port": 44818, "latency_ms": latency}
        try:
            info = self.plc_time()
            result["cip_status"] = info.Status
            result["plc_time"] = str(info.Value) if info.Status == "Success" else None
        except Exception as exc:
            result["cip_status"] = "Error"
            result["cip_error"] = str(exc)
        return result
