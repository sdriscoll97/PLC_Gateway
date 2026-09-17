"""PLCSession-compatible HTTP adapter for the migrated Expander GUI."""
from __future__ import annotations
import threading
from gateway_client import GatewayClient,GatewayError
class Response:
    def __init__(self,tag,value=None,status='Success'):self.TagName=tag;self.Value=value;self.Status=status
class GatewaySession:
    def __init__(self,name,client):
        self.name=name;self.client=client;self.ip='Gateway';self.slot=0;self.micro800=False;self.connection_size=None;self.comm=None;self.connected=False;self.connecting=False;self.last_error='';self.plc_time='';self.active_connection_size=None;self.lock=threading.RLock();self.read_inflight=False;self.all_tags=[];self.tag_display_map={};self.raw_tag_names=[]
    @property
    def slot_label(self):return 'Gateway'
    def _lost(self,exc):
        if isinstance(exc,GatewayError) and exc.kind in ('gateway_unavailable','gateway_timeout','gateway_invalid_response'):
            self.connected=False;self.read_inflight=False;self.last_error=str(exc)
        return exc
    def connect(self,status_cb=None):
        self.connecting=True
        try:
            if status_cb:status_cb('[%s] validating gateway...'%self.name)
            health=self.client.health()
            if self.name not in (health.get('configured_plcs') or []):raise RuntimeError('PLC is not configured on gateway')
            diag=self.client.diagnostics(self.name)
            if not diag.get('success',False):raise RuntimeError(str(diag))
            self.connected=True;self.plc_time=str(diag.get('plc_time',''));self.last_error='';return True,self.plc_time
        except Exception as exc:self.connected=False;self.last_error=str(exc);return False,self.last_error
        finally:self.connecting=False
    def teardown(self):self.connected=False;self.read_inflight=False
    def clear_tag_list(self):self.all_tags=[];self.tag_display_map={};self.raw_tag_names=[]
    def load_tag_list(self):
        try:payload=self.client.browse(self.name,limit=2000)
        except Exception as exc:raise self._lost(exc)
        rows=payload.get('tags',payload.get('items',[]));entries=[]
        for row in rows:
            full=row.get('name',row.get('tag_name',''));dtype=row.get('datatype',row.get('data_type','?')) or '?';scope='Controller';short=full
            if full.startswith('Program:'):rest=full[len('Program:'):];prog,_,tag=rest.partition('.');scope=prog;short=tag or rest
            entries.append(('%s    [%s]    (%s)'%(short,dtype,scope),full))
        entries.sort(key=lambda e:e[0].lower());self.all_tags=[d for d,_ in entries];self.tag_display_map=dict(entries);self.raw_tag_names=[r for _,r in entries];return sum(1 for d in self.all_tags if d.endswith('(Controller)')),sum(1 for d in self.all_tags if not d.endswith('(Controller)'))
    def read(self,tags):
        if isinstance(tags,str):tags=[tags]
        if not self.connected:raise RuntimeError('[%s] not connected.'%self.name)
        try:
            if len(tags)==1:
                row=self.client.read(self.name,tags[0]);return [Response(tags[0],row.get('value'),row.get('status','Success' if row.get('success') else 'Error'))]
            payload=self.client.read_batch(self.name,tags);rows=payload.get('items') or [];by_tag={row.get('tag'):row for row in rows if isinstance(row,dict) and row.get('tag')};return [Response(tag,by_tag.get(tag,{}).get('value'),by_tag.get(tag,{}).get('status','No response')) for tag in tags]
        except Exception as exc:raise self._lost(exc)
    def read_map(self,tags):return dict(zip(tags,self.read(tags)))
    def write(self,tag,value,verify_tag=None):
        if not self.connected:raise RuntimeError('[%s] not connected.'%self.name)
        try:row=self.client.write(self.name,tag,value,verify_tag);return Response(tag,row.get('value'),row.get('status','Success' if row.get('success') else 'Error'))
        except Exception as exc:raise self._lost(exc)
class GatewaySessionManager:
    def __init__(self,base_url,timeout=8.0,authenticated_user=None):
        self.client=GatewayClient(base_url,timeout,authenticated_user);health=self.client.health();self.sessions={name:GatewaySession(name,self.client) for name in health.get('configured_plcs',[])}
    def __iter__(self):return iter(self.sessions.values())
    def __getitem__(self,name):return self.sessions[name]
    def get(self,name):return self.sessions.get(name)
    def names(self):return list(self.sessions.keys())
    def connected_names(self):return [s.name for s in self.sessions.values() if s.connected]
    def connected_sessions(self):return [s for s in self.sessions.values() if s.connected]
    def teardown_all(self):
        for session in self.sessions.values():session.teardown()
