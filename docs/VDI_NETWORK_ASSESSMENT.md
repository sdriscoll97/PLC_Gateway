# VDI network access assessment

Status: documentation-only exploration; no deployment or network changes.
Branch: `explore/vdi-network-access`.

## Purpose

Retire any unapproved workstation-to-PLC path and assess an IT/OT-approved VDI access design. This document does not determine legality or establish company authorization. Changing VLANs alone does not establish authorization.

## Repository evidence

The existing project handoff records VLAN 617 as the PLC-facing network and VLAN 801 as BMX13's other interface. Neither is identified as the VDI-client VLAN. These are historical observations, not a current network inventory.

The existing architecture is workstation GUI -> HTTPS gateway -> PLC, with PLC addresses on the gateway and no direct workstation CIP access. Preserve this separation. The README requires an approved HTTPS/authentication deployment and defaults to read-only. A gateway is not automatically approved merely because it avoids direct CIP.

## Disconnect the existing path

1. Identify whether "direct connection" means a dedicated Ethernet cable, routed workstation CIP, or the gateway API.
2. If the application participates in active control, coordinate a safe machine state with the operator before interrupting it.
3. Stop GUI polling/writes and close all related GUI/watch windows. Stop any specifically identified client background task; do not indiscriminately terminate Python or disable shared services.
4. For a dedicated workstation-to-PLC cable, disconnect at the workstation end. Leave PLC power, controller mode, switch uplinks, and other PLC cables alone.
5. For a shared network/routed path, close the application and have IT/OT remove the specific unapproved route or access rule. Do not disable a shared NIC or delete routes by guesswork.
6. If withdrawing the gateway itself, identify its actual service/task and other consumers first. Have its owner stop it and prevent automatic restart as appropriate. The repository's remove_service.ps1 only prints guidance; it does not stop a service.
7. Verify the relevant application/process or service has stopped and the dedicated adapter is disconnected if applicable. Physical disconnection only removes that cable's path; it does not prove alternate routes are absent. Confirm removal of network access with IT/OT. Preserve logs and configuration.

## Collect local information without contacting PLCs

Run the following in PowerShell on the physical workstation, and separately inside the VDI desktop if available. Label the two outputs separately.

```powershell
hostname
Get-NetAdapter | Format-Table Name, InterfaceDescription, Status, ifIndex
Get-NetIPConfiguration
route print -4
```

These commands inspect local configuration; they do not scan networks or alter configuration. They can identify subnets and interfaces, but an IP subnet or adapter label does not independently prove a switch VLAN assignment. Have networking staff map the endpoint/switch port to its actual VLAN. Keep infrastructure output in an approved internal channel; do not commit it to this public repository.

## Candidate designs for review

| Option | Application placement | Required approved path |
| --- | --- | --- |
| GUI inside VDI | Virtual desktop/session host | VDI session host -> authenticated HTTPS gateway -> allowlisted PLCs |
| GUI on physical workstation | Physical workstation | Workstation -> authenticated HTTPS gateway -> allowlisted PLCs |

In the first option, the physical client provides the remote display/input session. Its VLAN need not be the VLAN used by the virtual desktop for application traffic. Do not infer that a physical VDI client can reach PLCs because an application inside its desktop can.

IT/OT must confirm:
- VDI product, physical-client VLAN, session-host VLAN, and supported application placement.
- Whether BMX13 is an approved gateway host or another managed host is required.
- Approved gateway DNS name, TLS certificate, authentication, source restrictions, and destination port.
- Exact gateway-to-PLC destinations and required protocol access.
- Network ownership, change procedure, and explicit read/write authorization.

Do not change VLAN tags, add routes, bridge adapters, enable forwarding, or substitute a tunnel to obtain an unapproved path.

## Validation after the design is approved

1. Validate the approved gateway's TLS identity and authentication from the selected application host.
2. Validate gateway health and one allowlisted read with the controls owner.
3. Verify unauthorized identities are denied and the application has no direct PLC fallback.
4. Verify workstation direct PLC access is absent through firewall policy review and any narrowly scoped tests approved by IT/OT.
5. Keep writes disabled throughout initial validation.
6. Record deployment and rollback details without publishing site-specific evidence.

## Open decisions

- Which connection is being withdrawn: dedicated cable, direct CIP over routing, or gateway API?
- Will the GUI run inside VDI or on the physical workstation?
- Which network and application placement does IT/OT approve?

## References

- [Existing project handoff](../PLC_Gateway_Service_Project_Handoff.md)
- [Deployment runbook](DEPLOYMENT_RUNBOOK.md)
- [Security notes](SECURITY.md)
- [Microsoft: Azure Virtual Desktop network connectivity](https://learn.microsoft.com/en-us/azure/virtual-desktop/network-connectivity) illustrates the distinction between client and session host; it does not identify the site's VDI product.
