PLC GATEWAY SERVICE
Project Handoff and Build Plan
Centralized Rockwell PLC access through BBCMWPBMX13

Prepared for: Engineering implementation agent
Environment: Milwaukee Brewery OT / Controls Network
Prepared from validated connectivity tests and the agreed implementation plan

CONFIDENTIAL - INTERNAL TECHNICAL HANDOFF
 
1. Executive Summary
The current Pylogix GUI cannot communicate directly with Rockwell PLCs when run from the workstation because the workstation is not connected to, and has no reachable route into, the PLC network. Testing confirmed that BBCMWPBMX13 can reach the required PLC endpoint over EtherNet/IP while the workstation cannot.
Validated Connectivity Findings
System	Network / interface	Observed result
Workstation	Source: 172.23.74.39 (Ethernet 3)	No 10.160.x.x route; ping to 10.160.12.10 failed; TCP 44818 failed; 10.160.12.60 also unreachable
BBCMWPBMX13	VLAN 801: 10.32.27.60/24
VLAN 617: 10.160.12.60/24	Ping to 10.160.12.10 succeeded; TCP 44818 succeeded; traffic sourced from VLAN 617
Target PLC	10.160.12.10	Reachable from BBCMWPBMX13 on EtherNet/IP TCP 44818

Current conclusion:
•	Pylogix is behaving correctly; the workstation failure occurs before a CIP session can be established.
•	The workstation has no direct path to the 10.160.12.0/24 PLC subnet.
•	BBCMWPBMX13 is dual-homed and has direct access through VLAN 617.
•	The preferred design is a centralized PLC Gateway service on BBCMWPBMX13 instead of extending VLAN 617 access to individual workstations.
Reference: BMX13_and_BMX14 Routes.docx contains the captured BMX13/BMX14 route tables and network interfaces.
2. Desired Architecture
Replace direct workstation-to-PLC communications with a client/server model. All EtherNet/IP traffic originates from BBCMWPBMX13.
CURRENT
Workstation GUI  -->  EtherNet/IP  -->  BLOCKED  -->  Rockwell PLC

TARGET
Workstation GUI  -->  HTTPS / REST  -->  BBCMWPBMX13 PLC Gateway
                                      |
                                      +--> Pylogix / EtherNet-IP --> Rockwell PLCs
3. Project Goals
1.	Create a centralized API service running on BBCMWPBMX13.
2.	Communicate directly with brewery Rockwell PLCs using Pylogix.
3.	Expose controlled REST endpoints for PLC reads, writes, browsing, object search, and diagnostics.
4.	Allow the existing GUI to function from a workstation without direct PLC network access.
5.	Centralize PLC definitions, access control, audit logging, diagnostics, and error handling.
6.	Support the PLCs currently reachable from BBCMWPBMX13.
7.	Keep the workstation GUI as a thin client and progressively move PLC business logic to the server.
4. Recommended Technology Stack
Layer	Preferred technology	Notes
API service	Python 3.x + FastAPI	Flask is an acceptable alternative, but FastAPI is preferred for validation and generated API documentation.
PLC communications	Pylogix	All PLC connections originate from BBCMWPBMX13.
Initial hosting	Windows Service	Service should start automatically and recover after server restart.
Production exposure	HTTPS reverse proxy	IIS reverse proxy is preferred in a Windows environment; Nginx is an alternative.
Configuration	External JSON or environment-specific configuration	Do not hard-code PLC IP addresses in the GUI.
Audit destination	SQL Server	Use an approved existing database or a dedicated database/schema after review.

5. Proposed Folder Structure
PLCGateway/
|-- api/
|   |-- read.py
|   |-- write.py
|   |-- browse.py
|   `-- diagnostics.py
|-- plc/
|   |-- plc_manager.py
|   |-- plc_config.json
|   `-- pylogix_wrapper.py
|-- audit/
|   |-- sql_logger.py
|   `-- audit_models.py
|-- logs/
|-- app.py
|-- requirements.txt
`-- README.md
6. PLC Configuration
Store PLC definitions externally and reference PLCs by logical name. The client GUI must not contain the PLC IP addresses directly.
{
  "PLC_6": {
    "ip": "10.160.12.10",
    "description": "Brewing PLC 6"
  },
  "PLC_10": {
    "ip": "10.160.12.20",
    "description": "Brewing PLC 10"
  }
}
Implementation note: the PLC_10 address above is an example placeholder and must be replaced with the validated PLC definition before deployment.
7. Required API Endpoints
7.1 Read Tag
GET /read?plc=PLC_6&tag=SomeTag
Example response:
{
  "success": true,
  "tag": "SomeTag",
  "value": 123,
  "datatype": "DINT"
}
7.2 Write Tag with Read-Back Verification
POST /write

{
  "plc": "PLC_6",
  "tag": "SomeTag",
  "value": 55
}
After the write, the service must read the target tag, compare the actual and expected values, and return the verification result.
{
  "success": true,
  "expected": 55,
  "actual": 55,
  "verified": true
}
7.3 Batch Reads
Batch reads are required for acceptable GUI performance and should reuse a single PLC connection where practical.
POST /read/batch

{
  "plc": "PLC_6",
  "tags": ["Tag1", "Tag2", "Tag3"]
}
{
  "success": true,
  "results": {
    "Tag1": 1,
    "Tag2": 2,
    "Tag3": 3
  }
}
7.4 Object Search
Support the existing GUI object-search workflow, including Brewmaxx class and record searches such as C512 and C588.
GET /objects?plc=PLC_6&class=C512
[
  {
    "class": "C512",
    "record": 1582,
    "path": "DiTSystemData.ClassObjects.C512[1582]"
  }
]
7.5 Browse
GET /browse?plc=PLC_6
Return the PLC tag/object hierarchy in a client-friendly structure. If browsing is expensive, support caching, pagination, or server-side filtering.
7.6 Diagnostics
GET /diagnostics?plc=PLC_6
{
  "reachable": true,
  "tcp_port": 44818,
  "latency_ms": 1,
  "firmware": "x.x"
}
Only return firmware or controller metadata when Pylogix or another approved method can retrieve it reliably. Do not fabricate unavailable values.
8. Authentication and Authorization
Initial deployment may be restricted to approved internal brewery network hosts, but network location alone should not be considered sufficient for write authorization.
Preferred end state:
•	Use Windows Authentication or an approved Active Directory-integrated authentication method.
•	Grant read operations to approved users or groups.
•	Restrict write operations to a dedicated, OT-approved Active Directory group.
•	Reject unknown PLC names, tags outside allowed patterns, unsupported datatypes, and unauthorized write requests.
•	Do not expose a generic proxy that permits arbitrary IP addresses or unrestricted CIP operations.
9. Audit Logging
Every write operation, including failed and denied attempts, should produce an auditable record. At minimum, capture:
•	UTC timestamp
•	Authenticated user
•	Client host or source address
•	PLC logical name and IP
•	Tag name
•	Old value
•	Requested new value
•	Write result
•	Read-back value and verification result
•	Request/correlation ID
•	Error details when applicable
Proposed SQL table:
CREATE TABLE dbo.PLCWriteAudit
(
    AuditID           BIGINT IDENTITY(1,1) PRIMARY KEY,
    TimestampUtc      DATETIME2(3) NOT NULL,
    UserName          NVARCHAR(256) NOT NULL,
    ClientHost        NVARCHAR(256) NULL,
    PLCName           NVARCHAR(100) NOT NULL,
    PLCAddress        VARCHAR(45) NOT NULL,
    TagName           NVARCHAR(512) NOT NULL,
    OldValue          NVARCHAR(MAX) NULL,
    RequestedValue    NVARCHAR(MAX) NULL,
    ActualValue       NVARCHAR(MAX) NULL,
    WriteSucceeded    BIT NOT NULL,
    Verified          BIT NULL,
    CorrelationID     UNIQUEIDENTIFIER NOT NULL,
    ErrorDetail       NVARCHAR(MAX) NULL
);
The table name, database, retention period, and access permissions must be reviewed before production deployment.
10. Client GUI Changes
Current communication path:
GUI --> Pylogix --> Direct PLC connection
Target communication path:
GUI --> HTTPS REST client --> PLC Gateway --> Pylogix --> PLC
Refactoring expectations:
•	Create a gateway client class that encapsulates HTTP calls, timeouts, authentication, JSON parsing, and server errors.
•	Replace direct PLC read, write, browse, object search, diagnostics, and read-back calls with gateway client methods.
•	Preserve existing UI workflows where possible so the transport change is transparent to the operator.
•	Provide clear error messages that distinguish gateway unavailability, authentication failure, invalid requests, PLC network failure, and PLC/CIP errors.
•	Keep an optional direct-connection mode only for controlled server-side testing, not as the normal workstation path.
11. Reliability and Safety Requirements
•	Use explicit connection and request timeouts. Never allow calls to hang indefinitely.
•	Limit concurrent operations per PLC and prevent connection storms.
•	Use connection reuse or a controlled connection manager where Pylogix behavior permits.
•	Apply server-side allowlists for PLCs and, where practical, writable tags or tag patterns.
•	Default the service to read-only until write authorization and auditing are validated.
•	Use structured rotating logs and avoid logging secrets.
•	Add a health endpoint that checks the gateway process separately from individual PLC reachability.
•	Use HTTPS for workstation-to-gateway traffic before production use.
•	Provide graceful shutdown and automatic service recovery.
•	Do not perform automatic write retries unless the operation is proven safe and idempotent.
12. Suggested Delivery Phases
Phase	Scope	Exit condition
1 - Read-only proof of concept	FastAPI service, PLC config, /health, /read, /read/batch, basic logs	Workstation reads PLC_6 through BMX13 without direct VLAN 617 access.
2 - GUI integration	Gateway client class; replace direct read/browse/object-search/diagnostics calls	Existing read-only GUI workflows operate through the gateway.
3 - Controlled writes	Authentication, authorization, allowlists, SQL audit, write and read-back verification	Approved user can perform an audited write; unauthorized user is denied.
4 - Production hardening	HTTPS, Windows Service, recovery, monitoring, deployment/runbook, testing	Service survives reboot, failures are observable, and support documentation is complete.

13. Primary Success Criteria
•	☐ The GUI runs from the 172.23.74.x workstation network.
•	☐ The GUI can read PLC tags through BBCMWPBMX13.
•	☐ The GUI can perform approved writes through BBCMWPBMX13.
•	☐ Write operations are verified by immediate read-back.
•	☐ No workstation requires direct VLAN 617 access.
•	☐ All EtherNet/IP PLC traffic originates from BBCMWPBMX13.
•	☐ All writes and denied write attempts are auditable.
•	☐ PLC addresses and security rules are centrally managed.
•	☐ Failures are returned as structured, actionable API errors.
14. Agent Build Deliverables
•	☐ Complete FastAPI source code with modular routing and Pylogix wrapper.
•	☐ Example and production-ready configuration templates with secrets excluded.
•	☐ Gateway HTTP client class for integration into the existing Pylogix GUI.
•	☐ Windows Service installation and removal scripts or documented service wrapper procedure.
•	☐ SQL audit table script and data-access implementation.
•	☐ Automated tests using mocks so tests do not write to a live PLC.
•	☐ Controlled integration-test checklist for BBCMWPBMX13 and PLC_6.
•	☐ API documentation with example requests, responses, and error schemas.
•	☐ Deployment, rollback, troubleshooting, and support runbook.
•	☐ Security notes identifying authentication, authorization, allowlist, certificate, and service-account decisions still requiring approval.
15. Constraints and Guardrails
•	Do not change workstation routing or attach workstations directly to VLAN 617 as part of this build.
•	Do not assign additional IP addresses to BBCMWPBMX13 without the normal infrastructure change process.
•	Do not enable unrestricted arbitrary-IP or arbitrary-tag access.
•	Do not test write operations against production tags without an approved test tag and change window.
•	Do not place credentials, API keys, SQL passwords, or certificate private keys in source control.
•	Preserve the GUI verify-by-read-back behavior.
16. Long-Term Vision
Use BBCMWPBMX13 as a controlled, centralized brewery PLC access gateway so approved engineering applications can interact with Rockwell PLCs without direct workstation access to the controls VLAN. The gateway becomes the standard interface layer for the existing GUI and may later support other approved diagnostics or reporting clients, subject to security and operations review.
17. Starting Point for the Build Agent
8.	Create a read-only FastAPI proof of concept on BBCMWPBMX13 with /health, /read, and /read/batch.
9.	Use PLC_6 at 10.160.12.10 as the first validated connectivity target.
10.	Bind the service only to the approved BMX13-facing interface and port selected during deployment review.
11.	Demonstrate a workstation request reaching the gateway and returning a PLC value.
12.	Integrate a gateway client class into the existing GUI without changing the operator workflow.
13.	Add writes only after authentication, authorization, allowlisting, SQL auditing, and a safe test tag are available.
