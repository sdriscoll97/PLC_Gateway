# PLC Gateway deployment and support runbook

## Safety defaults
The checked-in configuration is read-only. Do not change it until AD authorization, SQL audit, a writable-tag allowlist, and an approved test tag/change window exist. Workstations must not be attached to VLAN 617.

## BMX13 deployment
1. Use 64-bit Python 3.12+ on BBCMWPBMX13 and create `.venv`.
2. Install `requirements.txt`.
3. Copy `PLCGateway/plc/plc_config.production.example.json` outside source control, validate PLC addresses, then set `PLC_GATEWAY_CONFIG` to that file.
4. Set `PLC_GATEWAY_AUDIT_SQL` only after the approved SQL audit table exists. Never commit the connection string.
5. First run Uvicorn bound to `127.0.0.1`; validate `/health`, `/diagnostics?plc=PLC_6`, `/read`, and `/read/batch` locally.
6. During deployment review select the approved BMX13-facing address/port. The handoff identifies 10.32.27.60 as VLAN 801 and 10.160.12.60 as VLAN 617; do not expose the API on the controls-facing interface by accident.
7. Put IIS HTTPS/reverse proxy and AD-integrated authentication in front of Uvicorn before production workstation use. Configure IIS to remove client-supplied `X-Authenticated-User` and inject only the authenticated Windows identity.
8. Install as an automatically starting Windows service using the organization's approved wrapper and configure recovery after failure.

## Read-only integration test
From BMX13: verify TCP 44818 to PLC_6, start the gateway, then call `/health`, `/diagnostics?plc=PLC_6`, `/read?plc=PLC_6&tag=<approved-readable-tag>`, and `/read/batch` with approved read-only tags. From the 172.23.74.x workstation, call the HTTPS gateway URL and verify the same values without any direct 10.160.12.x route.

## Controlled write test
Only in an approved change window: create the SQL audit table, configure the service account, AD write identity/group integration, and an exact writable-tag regex for the approved test tag. Set `read_only` false only for this test. POST `/write`, confirm immediate read-back and the matching SQL row (old/requested/actual values, user, client, PLC, verification and correlation ID). Verify an unauthorized user and a non-allowlisted tag are denied and audited. Return to read-only if approval is incomplete.

## Troubleshooting
`gateway_unavailable`: test HTTPS/IIS/service status. `unknown_plc`: fix central config, never add an arbitrary-IP parameter. `plc_read_failed`/`cip_*`: run diagnostics on BMX13 and validate routing/TCP 44818/slot. `object_search_failed`: validate ODBC driver, Windows identity and SQL reachability. `write_denied`: inspect read-only mode, AD identity, allowlist and audit configuration. Logs rotate under `PLCGateway/logs`; secrets must never be logged.

## Rollback
Stop/disable the gateway service and IIS route, restore the previous application package/configuration, retain logs and SQL audit records, and leave workstation routing unchanged. No PLC write should be used as a rollback mechanism.
