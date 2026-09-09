from types import SimpleNamespace
from unittest.mock import Mock
import json
from pathlib import Path
from plc.config import GatewayConfig
from plc.plc_manager import PLCManager

class FakeWrapper:
    def __init__(self, definition, timeout=5): self.definition=definition; self.writes=[]
    def read(self,tags): return [SimpleNamespace(Status='Success',Value=i+1) for i,_ in enumerate(tags)]
    def write(self,tag,value): self.writes.append((tag,value)); return SimpleNamespace(Status='Success')
    def tag_list(self): return SimpleNamespace(Status='Success',Value=[])
    def diagnostics(self): return {'reachable':True,'tcp_port':44818,'latency_ms':1}
    def close(self): pass

def config(tmp_path):
    path=tmp_path/'cfg.json'; path.write_text(json.dumps({'read_only':True,'plcs':{'PLC_6':{'ip':'10.160.12.10','writable_tag_patterns':['^Safe$']}}}))
    return GatewayConfig(path)

def test_batch_read_reuses_managed_wrapper(tmp_path):
    m=PLCManager(config(tmp_path),wrapper_factory=FakeWrapper)
    result=m.read('PLC_6',['A','B']); assert [r.Value for r in result]==[1,2]

def test_unknown_plc_rejected(tmp_path):
    m=PLCManager(config(tmp_path),wrapper_factory=FakeWrapper)
    try: m.read('10.160.12.99',['A']); assert False
    except KeyError: pass

def test_write_allowlist_is_anchored(tmp_path):
    m=PLCManager(config(tmp_path),wrapper_factory=FakeWrapper)
    assert m.allowed_write('PLC_6','Safe'); assert not m.allowed_write('PLC_6','Safe.Extra')
