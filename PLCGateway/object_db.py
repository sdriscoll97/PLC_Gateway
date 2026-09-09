from __future__ import annotations
import os
from dataclasses import dataclass
try: import pyodbc
except ImportError: pyodbc=None

@dataclass
class ObjectRow:
    data_xlink:int; designation:str; class_no:int; station_no:int|None; record_no:int

class ObjectDB:
    def __init__(self): self._conn=None
    def connect(self):
        if pyodbc is None: raise RuntimeError("pyodbc is not installed")
        cs=os.environ.get("PLC_GATEWAY_OBJECT_SQL","")
        if not cs: raise RuntimeError("PLC_GATEWAY_OBJECT_SQL is not configured")
        if self._conn is None: self._conn=pyodbc.connect(cs,timeout=10); self._conn.timeout=30
        return self._conn
    def close(self):
        if self._conn:
            try:self._conn.close()
            finally:self._conn=None
    def fetch_object(self,plc_name,class_num=None,record_no=None):
        # SQL source/column names match the existing GUI's validated vwDSCPDataX workflow.
        sql="SELECT nDataXLink, szDesignation, nClassNo, nStationNo, nRecordNo FROM dbo.vwDSCPDataX WHERE 1=1"
        params=[]
        if class_num is not None: sql+=" AND nClassNo=?"; params.append(class_num)
        if record_no is not None: sql+=" AND nRecordNo=?"; params.append(record_no)
        # PLC-to-station mapping is external so the API never accepts arbitrary SQL identifiers.
        station_map={k:int(v) for k,v in __import__('json').loads(os.environ.get('PLC_GATEWAY_STATIONS','{}')).items()}
        if plc_name in station_map: sql+=" AND nStationNo=?"; params.append(station_map[plc_name])
        sql+=" ORDER BY nRecordNo"
        cur=self.connect().cursor(); cur.execute(sql,*params); rows=cur.fetchall(); cur.close()
        return [ObjectRow(int(r[0]),(r[1] or '').strip(),int(r[2]),None if r[3] is None else int(r[3]),int(r[4])) for r in rows]
