"""HTTP transport for the workstation GUI. Contains no PLC IP addresses."""
from __future__ import annotations
import json, urllib.error, urllib.parse, urllib.request

class GatewayError(RuntimeError):
    def __init__(self, kind, message, status=None): super().__init__(message); self.kind=kind; self.status=status

class GatewayClient:
    def __init__(self, base_url, timeout=8.0, authenticated_user=None):
        self.base_url=base_url.rstrip('/'); self.timeout=timeout; self.authenticated_user=authenticated_user

    def _request(self, method, path, params=None, body=None):
        url=self.base_url+path
        if params: url+='?'+urllib.parse.urlencode(params)
        data=None if body is None else json.dumps(body).encode('utf-8')
        headers={'Accept':'application/json'}
        if data is not None: headers['Content-Type']='application/json'
        if self.authenticated_user: headers['X-Authenticated-User']=self.authenticated_user
        try:
            with urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers,method=method),timeout=self.timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            try: payload=json.loads(exc.read().decode('utf-8')); detail=payload.get('detail',payload)
            except Exception: detail={}
            code=detail.get('code','http_error') if isinstance(detail,dict) else 'http_error'
            msg=detail.get('message',str(detail)) if isinstance(detail,dict) else str(detail)
            raise GatewayError(code,msg,exc.code) from exc
        except urllib.error.URLError as exc: raise GatewayError('gateway_unavailable',str(exc.reason)) from exc
        except TimeoutError as exc: raise GatewayError('gateway_timeout',str(exc)) from exc

    def health(self): return self._request('GET','/health')
    def read(self,plc,tag): return self._request('GET','/read',{'plc':plc,'tag':tag})
    def read_batch(self,plc,tags): return self._request('POST','/read/batch',body={'plc':plc,'tags':list(tags)})
    def browse(self,plc,q='',limit=500,offset=0): return self._request('GET','/browse',{'plc':plc,'q':q,'limit':limit,'offset':offset})
    def schema(self,plc,q='',limit=500,offset=0): return self._request('GET','/schema',{'plc':plc,'q':q,'limit':limit,'offset':offset})
    def expand(self,plc,path,limit=100,offset=0): return self._request('GET','/schema/expand',{'plc':plc,'path':path,'limit':limit,'offset':offset})
    def schema_type(self,plc,type_name):
        return self._request('GET','/schema/type/'+urllib.parse.quote(type_name,safe=''),{'plc':plc})
    def objects(self,plc,class_name=None,record=None):
        params={'plc':plc};
        if class_name is not None: params['class']=class_name
        if record is not None: params['record']=record
        return self._request('GET','/objects',params)
    def diagnostics(self,plc): return self._request('GET','/diagnostics',{'plc':plc})
    def write(self,plc,tag,value,verify_tag=None):
        body={'plc':plc,'tag':tag,'value':value}
        if verify_tag: body['verify_tag']=verify_tag
        return self._request('POST','/write',body=body)
