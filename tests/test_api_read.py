from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PLCGateway.api.read import router

class Manager:
    def read(self,plc,tags): return [SimpleNamespace(Status='Success',Value=7) for _ in tags]

def test_read_and_batch_without_live_plc():
    app=FastAPI(); app.include_router(router); app.state.manager=Manager(); c=TestClient(app)
    r=c.get('/read',params={'plc':'PLC_6','tag':'A'}); assert r.status_code==200 and r.json()['value']==7
    r=c.post('/read/batch',json={'plc':'PLC_6','tags':['A','B']}); assert r.status_code==200 and r.json()['results']=={'A':7,'B':7}
