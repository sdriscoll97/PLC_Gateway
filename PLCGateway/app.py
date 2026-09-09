from contextlib import asynccontextmanager
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from api.read import router as read_router
from api.write import router as write_router
from api.browse import router as browse_router
from api.diagnostics import router as diagnostics_router
from api.objects import router as objects_router
from plc.config import GatewayConfig
from plc.plc_manager import PLCManager
from audit.sql_logger import SQLAuditLogger
from plantit_db import PlantItDB
import plc_config as legacy_cfg

LOG_DIR=Path(__file__).resolve().parent/"logs"; LOG_DIR.mkdir(exist_ok=True)
handler=RotatingFileHandler(LOG_DIR/"gateway.log",maxBytes=5_000_000,backupCount=5,encoding="utf-8")
logging.basicConfig(level=logging.INFO,handlers=[handler,logging.StreamHandler()],format="%(asctime)s %(levelname)s %(name)s %(message)s")

@asynccontextmanager
async def lifespan(app):
    config=GatewayConfig(); app.state.config=config; app.state.manager=PLCManager(config)
    app.state.audit=SQLAuditLogger(config.sql_audit_connection)
    app.state.object_db=PlantItDB(server=legacy_cfg.SQL13_SERVER,database=legacy_cfg.DBIDC_DATABASE)
    yield
    app.state.manager.close(); app.state.object_db.close()

app=FastAPI(title="PLC Gateway",version="1.0.0",lifespan=lifespan)
app.include_router(read_router); app.include_router(write_router); app.include_router(browse_router)
app.include_router(diagnostics_router); app.include_router(objects_router)

@app.get("/health",tags=["health"])
def health(request:Request):
    return {"success":True,"service":"PLC Gateway","read_only":request.app.state.config.read_only,
            "configured_plcs":request.app.state.manager.names()}

@app.exception_handler(Exception)
async def unhandled(_request,exc):
    logging.getLogger("gateway").exception("Unhandled request error")
    return JSONResponse(status_code=500,content={"success":False,"error":{"code":"internal_error","message":str(exc)}})
