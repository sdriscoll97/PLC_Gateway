# PLC Gateway

Centralized Rockwell PLC access service for BBCMWPBMX13 plus the migrated PYLOGIX GUI Expander source. The architecture and guardrails come from `PLC_Gateway_Service_Project_Handoff.md`.

## Current safety state
The committed gateway configuration is **read-only**. PLC addresses live only in server configuration. Workstation clients use `gateway_client.py` and must not require a direct 10.160.12.x route. The write endpoint exists for controlled commissioning but is denied until read-only is disabled, an authenticated identity is approved, an exact server-side tag allowlist is present, and required SQL auditing is configured.

## Server quick start (BBCMWPBMX13)
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PLC_GATEWAY_CONFIG = "$PWD\PLCGateway\plc\plc_config.json"
.\.venv\Scripts\python.exe -m uvicorn PLCGateway.app:app --host 127.0.0.1 --port 8443
```
Then open `http://127.0.0.1:8443/health` and `/docs` locally. Do not expose plain HTTP to workstations; production uses an approved IIS HTTPS reverse proxy/Windows Authentication design.

## Tests
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -m pytest -q tests
```
Mock tests never write to a live PLC. Controlled plant validation is documented in `docs/DEPLOYMENT_RUNBOOK.md`.

## Repository layout
`PLCGateway/` is the FastAPI service. `gateway_client.py` is the thin workstation transport. `audit/` contains SQL auditing. `tests/` contains offline mocks. The migrated GUI files remain at repository root. See `docs/API.md`, `docs/SECURITY.md`, and `docs/DEPLOYMENT_RUNBOOK.md`.

## Windows service
Run `scripts/install_service.ps1` to prepare the virtual environment and print the approved service-wrapper command values. The organization must choose/approve NSSM, WinSW, or its standard Windows service wrapper. Configure automatic start and recovery. `scripts/remove_service.ps1` documents rollback expectations.
