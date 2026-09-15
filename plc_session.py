"""Compatibility shim: legacy GUI session imports now use BMX13 HTTP only."""
from __future__ import annotations
import os
from gateway_session import GatewaySession, GatewaySessionManager, Response

class SessionManager(GatewaySessionManager):
    """Accept the legacy cfg.PLCS argument but never use PLC IPs on the client."""
    def __init__(self, _legacy_plcs=None, base_url=None, timeout=8.0, authenticated_user=None):
        url = base_url or os.environ.get('PLC_GATEWAY_URL', 'http://10.32.27.60:8443')
        super().__init__(url, timeout=timeout, authenticated_user=authenticated_user)

PLCSession = GatewaySession
