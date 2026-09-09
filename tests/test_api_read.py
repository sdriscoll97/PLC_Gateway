from unittest.mock import Mock
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.read import router

def test_read_and_batch_without_live_plc():
    app=FastAPI(); app.include_router(router)
    manager=Mock(); manager.read.side_effect=lambda plc,tags:[SimpleNamespace(Status='Success',Value=7) for _ in tags]
    app.state.manager=manager
    c=TestClient(app)
    r=c.get('/read',params={'plc':'PLC_6','tag':'A'}); assert r.status_code==200 and r.json()['value']==7
    r=c.post('/read/batch',json={'plc':'PLC_6','tags':['A','B']}); assert r.status_code==200 and r.json()['results']=={'A':7,'B':7}
