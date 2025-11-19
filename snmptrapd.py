#!/usr/bin/env python3
"""
Simple SNMP trap/inform receiver used by the docker-snmpsim image.

It is based on the sample from snmpreceiver/snmptrapd.py but adjusted to
stream logs to stdout (better for containers) and expose a few environment
variables for configuration.
"""
import logging
import os
import sys
from typing import List, Sequence, Tuple, Union

from pysnmp.carrier.asyncore.dgram import udp
from pysnmp.entity import config, engine
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.hlapi import (
    usm3DESEDEPrivProtocol,
    usmAesCfb128Protocol,
    usmAesCfb192Protocol,
    usmAesCfb256Protocol,
    usmDESPrivProtocol,
    usmHMAC128SHA224AuthProtocol,
    usmHMAC192SHA256AuthProtocol,
    usmHMAC256SHA384AuthProtocol,
    usmHMAC384SHA512AuthProtocol,
    usmHMACMD5AuthProtocol,
    usmHMACSHAAuthProtocol,
    usmNoAuthProtocol,
    usmNoPrivProtocol,
)

TRAP_ADDRESS = os.environ.get("SNMPTRAPD_ADDRESS", "0.0.0.0")
TRAP_PORT = int(os.environ.get("SNMPTRAPD_PORT", "162"))
COMMUNITY = os.environ.get("SNMPTRAPD_COMMUNITY", "public")
LOG_FILE = os.environ.get("SNMPTRAPD_LOG_FILE")
LOG_LEVEL = os.environ.get("SNMPTRAPD_LOG_LEVEL", "INFO").upper()
V3_USERS_RAW = os.environ.get("SNMPTRAPD_V3_USERS", "").strip()

AUTH_PROTOCOLS = {
    "NONE": usmNoAuthProtocol,
    "MD5": usmHMACMD5AuthProtocol,
    "SHA": usmHMACSHAAuthProtocol,
    "SHA224": usmHMAC128SHA224AuthProtocol,
    "SHA256": usmHMAC192SHA256AuthProtocol,
    "SHA384": usmHMAC256SHA384AuthProtocol,
    "SHA512": usmHMAC384SHA512AuthProtocol,
}

PRIV_PROTOCOLS = {
    "NONE": usmNoPrivProtocol,
    "DES": usmDESPrivProtocol,
    "3DES": usm3DESEDEPrivProtocol,
    "AES128": usmAesCfb128Protocol,
    "AES192": usmAesCfb192Protocol,
    "AES256": usmAesCfb256Protocol,
}


def _format_address(address: Union[str, Sequence[object]]) -> str:
    if isinstance(address, (list, tuple)):
        return ":".join(str(part) for part in address)
    return str(address)


def _parse_v3_users(raw_value: str) -> List[Tuple[str, str, str, str, str]]:
    """
    Parse SNMPTRAPD_V3_USERS env value.

    Expected format: user:authProto:authKey:privProto:privKey;user2:...
    Proto strings match AUTH_PROTOCOLS/PRIV_PROTOCOLS keys.
    """
    entries: List[Tuple[str, str, str, str, str]] = []
    for chunk in raw_value.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split(":")
        while len(parts) < 5:
            parts.append("")
        username, auth_proto, auth_key, priv_proto, priv_key = parts[:5]
        if not username:
            logging.warning("Ignoring SNMPv3 user entry with empty username: %s", chunk)
            continue
        entries.append(
            (username.strip(), auth_proto.strip(), auth_key.strip(), priv_proto.strip(), priv_key.strip())
        )
    return entries


def _resolve_protocol(mapping, name: str, default):
    if not name:
        return default
    value = mapping.get(name.upper())
    if value is None:
        logging.error("Unknown protocol '%s'. Supported values: %s", name, ", ".join(sorted(mapping)))
    return value


def _configure_v3_users(snmp_engine: engine.SnmpEngine) -> None:
    if not V3_USERS_RAW:
        logging.info("No SNMPv3 users configured (set SNMPTRAPD_V3_USERS to add some)")
        return

    for username, auth_proto_name, auth_key, priv_proto_name, priv_key in _parse_v3_users(V3_USERS_RAW):
        auth_protocol = _resolve_protocol(AUTH_PROTOCOLS, auth_proto_name, usmNoAuthProtocol)
        if auth_protocol is None:
            continue
        priv_protocol = _resolve_protocol(PRIV_PROTOCOLS, priv_proto_name, usmNoPrivProtocol)
        if priv_protocol is None:
            continue

        if auth_protocol is usmNoAuthProtocol:
            auth_key = None
            if priv_protocol is not usmNoPrivProtocol:
                logging.error(
                    "SNMPv3 user '%s' requests privacy without authentication, which is not allowed. "
                    "Either specify an auth protocol/key or disable privacy.",
                    username,
                )
                continue
        elif not auth_key:
            logging.error("SNMPv3 user '%s' requires auth key for protocol %s", username, auth_proto_name or "UNKNOWN")
            continue

        if priv_protocol is usmNoPrivProtocol:
            priv_key = None
        elif not priv_key:
            logging.error("SNMPv3 user '%s' requires priv key for protocol %s", username, priv_proto_name or "UNKNOWN")
            continue

        config.addV3User(snmp_engine, username, auth_protocol, auth_key, priv_protocol, priv_key)
        logging.info(
            "Configured SNMPv3 user '%s' (auth=%s, priv=%s)",
            username,
            auth_proto_name.upper() if auth_proto_name else "NONE",
            priv_proto_name.upper() if priv_proto_name else "NONE",
        )


def main() -> None:
    log_kwargs = {
        "format": "%(asctime)s [%(levelname)s] %(message)s",
        "level": getattr(logging, LOG_LEVEL, logging.INFO),
    }
    if LOG_FILE:
        log_kwargs["filename"] = LOG_FILE
    else:
        log_kwargs["stream"] = sys.stdout
    logging.basicConfig(**log_kwargs)

    snmp_engine = engine.SnmpEngine()

    logging.info(
        "Starting PySNMP trap receiver on %s:%s (community=%s)",
        TRAP_ADDRESS,
        TRAP_PORT,
        COMMUNITY,
    )

    config.addTransport(
        snmp_engine,
        udp.domainName + (1,),
        udp.UdpTransport().openServerMode((TRAP_ADDRESS, TRAP_PORT)),
    )

    config.addV1System(snmp_engine, "trap-area", COMMUNITY)
    _configure_v3_users(snmp_engine)

    def cb_fun(snmp_engine, state_reference, context_engine_id, context_name, var_binds, cb_ctx):
        transport_domain, transport_address = snmp_engine.msgAndPduDsp.getTransportInfo(
            state_reference
        )
        logging.info(
            "Trap received from %s (%s)",
            _format_address(transport_address),
            transport_domain,
        )
        for name, val in var_binds:
            logging.info("%s = %s", name.prettyPrint(), val.prettyPrint())
        logging.info("==== End of Incoming Trap ====")

    ntfrcv.NotificationReceiver(snmp_engine, cb_fun)

    snmp_engine.transportDispatcher.jobStarted(1)

    try:
        snmp_engine.transportDispatcher.runDispatcher()
    except KeyboardInterrupt:
        logging.info("Trap receiver interrupted, shutting down")
    finally:
        snmp_engine.transportDispatcher.closeDispatcher()


if __name__ == "__main__":
    main()
