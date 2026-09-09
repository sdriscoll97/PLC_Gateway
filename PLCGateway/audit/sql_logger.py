"""SQL Server write-audit sink. Connection string is supplied only through environment."""
from __future__ import annotations
import json
try:
    import pyodbc
except ImportError:
    pyodbc = None

class AuditUnavailable(RuntimeError): pass

class SQLAuditLogger:
    INSERT = """INSERT INTO dbo.PLCWriteAudit
(TimestampUtc,UserName,ClientHost,PLCName,PLCAddress,TagName,OldValue,RequestedValue,
 ActualValue,WriteSucceeded,Verified,CorrelationID,ErrorDetail)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"""

    def __init__(self, connection_string=""):
        self.connection_string = connection_string

    @property
    def configured(self): return bool(self.connection_string)

    @staticmethod
    def _text(value):
        if value is None: return None
        try: return json.dumps(value, default=str)
        except TypeError: return str(value)

    def log(self, record):
        if not self.connection_string: raise AuditUnavailable("SQL audit is not configured")
        if pyodbc is None: raise AuditUnavailable("pyodbc is not installed")
        conn = pyodbc.connect(self.connection_string, timeout=10)
        try:
            cur = conn.cursor()
            cur.execute(self.INSERT, record.timestamp_utc, record.user_name, record.client_host,
                        record.plc_name, record.plc_address, record.tag_name,
                        self._text(record.old_value), self._text(record.requested_value),
                        self._text(record.actual_value), int(record.write_succeeded),
                        None if record.verified is None else int(record.verified),
                        str(record.correlation_id), record.error_detail)
            conn.commit()
        finally:
            conn.close()
