from types import SimpleNamespace
import json
from PLCGateway.plc.config import GatewayConfig
from PLCGateway.plc.plc_manager import PLCManager

class FakeWrapper:
    def __init__(self,definition,timeout=5): self.definition=definition; self.writes=[]
    def read(self,tags): return [SimpleNamespace(Status='Success',Value=i+1) for i,_ in enumerate(tags)]
    def write(self,tag,value): self.writes.append((tag,value)); return SimpleNamespace(Status='Success')
    def tag_list(self): return SimpleNamespace(Status='Success',Value=[])
    def diagnostics(self): return {'reachable':True,'tcp_port':44818,'latency_ms':1}
    def close(self): pass

def cfg(tmp_path):
    p=tmp_path/'cfg.json'; p.write_text(json.dumps({'read_only':True,'plcs':{'PLC_6':{'ip':'10.160.12.10','writable_tag_patterns':['^Safe$']}}})); return GatewayConfig(p)
def test_batch(tmp_path): assert [r.Value for r in PLCManager(cfg(tmp_path),FakeWrapper).read('PLC_6',['A','B'])]==[1,2]
def test_unknown(tmp_path):
    try: PLCManager(cfg(tmp_path),FakeWrapper).read('10.160.12.99',['A']); assert False
    except KeyError: pass
def test_allowlist(tmp_path):
    m=PLCManager(cfg(tmp_path),FakeWrapper); assert m.allowed_write('PLC_6','Safe'); assert not m.allowed_write('PLC_6','Safe.Extra')
