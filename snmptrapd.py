#!/usr/bin/env python3
"""
Simple SNMP trap/inform receiver used by the docker-snmpsim image.

It is based on the sample from snmpreceiver/snmptrapd.py but adjusted to
stream logs to stdout (better for containers) and expose a few environment
variables for configuration.
"""
import asyncio
import logging
import os
import sys
from typing import List, Sequence, Tuple, Union

from pysnmp import debug as pysnmp_debug
from pysnmp import error as pysnmp_error
from pysnmp.carrier.asyncio.dgram import udp
from pysnmp.entity import config, engine
from pysnmp.entity.rfc3413 import ntfrcv

EVENT_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(EVENT_LOOP)

TRAP_ADDRESS = os.environ.get("SNMPTRAPD_ADDRESS", "0.0.0.0")
TRAP_PORT = int(os.environ.get("SNMPTRAPD_PORT", "162"))
COMMUNITY = os.environ.get("SNMPTRAPD_COMMUNITY", "public")
LOG_FILE = os.environ.get("SNMPTRAPD_LOG_FILE")
LOG_LEVEL = os.environ.get("SNMPTRAPD_LOG_LEVEL", "INFO").upper()
V3_USERS_RAW = os.environ.get("SNMPTRAPD_V3_USERS", "").strip()
VACM_SUBTREE = (1, 3, 6)
PYSNMP_DEBUG = os.environ.get("SNMPTRAPD_PYSNMP_DEBUG", "").strip()

AUTH_PROTOCOLS = {
    "NONE": config.USM_AUTH_NONE,
    "MD5": config.USM_AUTH_HMAC96_MD5,
    "SHA": config.USM_AUTH_HMAC96_SHA,
    "SHA224": config.USM_AUTH_HMAC128_SHA224,
    "SHA256": config.USM_AUTH_HMAC192_SHA256,
    "SHA384": config.USM_AUTH_HMAC256_SHA384,
    "SHA512": config.USM_AUTH_HMAC384_SHA512,
}

PRIV_PROTOCOLS = {
    "NONE": config.USM_PRIV_NONE,
    "DES": config.USM_PRIV_CBC56_DES,
    "3DES": config.USM_PRIV_CBC168_3DES,
    "AES128": config.USM_PRIV_CFB128_AES,
    "AES192": config.USM_PRIV_CFB192_AES,
    "AES256": config.USM_PRIV_CFB256_AES,
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
        auth_protocol = _resolve_protocol(AUTH_PROTOCOLS, auth_proto_name, config.USM_AUTH_NONE)
        if auth_protocol is None:
            continue
        priv_protocol = _resolve_protocol(PRIV_PROTOCOLS, priv_proto_name, config.USM_PRIV_NONE)
        if priv_protocol is None:
            continue

        if auth_protocol == config.USM_AUTH_NONE:
            auth_key = None
            if priv_protocol != config.USM_PRIV_NONE:
                logging.error(
                    "SNMPv3 user '%s' requests privacy without authentication, which is not allowed. "
                    "Either specify an auth protocol/key or disable privacy.",
                    username,
                )
                continue
        elif not auth_key:
            logging.error("SNMPv3 user '%s' requires auth key for protocol %s", username, auth_proto_name or "UNKNOWN")
            continue

        if priv_protocol == config.USM_PRIV_NONE:
            priv_key = None
        elif not priv_key:
            logging.error("SNMPv3 user '%s' requires priv key for protocol %s", username, priv_proto_name or "UNKNOWN")
            continue

        config.add_v3_user(snmp_engine, username, auth_protocol, auth_key, priv_protocol, priv_key)
        security_level = "noAuthNoPriv"
        if auth_protocol != config.USM_AUTH_NONE and priv_protocol == config.USM_PRIV_NONE:
            security_level = "authNoPriv"
        elif auth_protocol != config.USM_AUTH_NONE and priv_protocol != config.USM_PRIV_NONE:
            security_level = "authPriv"
        config.add_vacm_user(
            snmp_engine,
            3,
            username,
            security_level,
            VACM_SUBTREE,
            VACM_SUBTREE,
            VACM_SUBTREE,
        )
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

    if PYSNMP_DEBUG:
        debug_topics = [topic.strip() for topic in PYSNMP_DEBUG.split(",") if topic.strip()]
        logging.info("Enabling PySNMP debug for topics: %s", ", ".join(debug_topics))
        try:
            pysnmp_debug.set_logger(pysnmp_debug.Debug(*debug_topics))
        except pysnmp_error.PySnmpError as exc:
            logging.error("Failed to enable PySNMP debug: %s", exc)

    snmp_engine = engine.SnmpEngine()

    logging.info(
        "Starting PySNMP trap receiver on %s:%s (community=%s)",
        TRAP_ADDRESS,
        TRAP_PORT,
        COMMUNITY,
    )
    logging.info("SNMP engineID: %s", snmp_engine.snmpEngineID.prettyPrint())

    config.add_transport(
        snmp_engine,
        udp.DOMAIN_NAME,
        udp.UdpTransport().open_server_mode((TRAP_ADDRESS, TRAP_PORT)),
    )

    config.add_v1_system(snmp_engine, "trap-area", COMMUNITY)
    config.add_vacm_user(
        snmp_engine, 1, "trap-area", "noAuthNoPriv", VACM_SUBTREE, VACM_SUBTREE, VACM_SUBTREE
    )
    config.add_vacm_user(
        snmp_engine, 2, "trap-area", "noAuthNoPriv", VACM_SUBTREE, VACM_SUBTREE, VACM_SUBTREE
    )
    _configure_v3_users(snmp_engine)

    def cb_fun(snmp_engine, state_reference, context_engine_id, context_name, var_binds, cb_ctx):
        transport_domain, transport_address = snmp_engine.message_dispatcher.get_transport_info(
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

    snmp_engine.transport_dispatcher.job_started(1)

    try:
        snmp_engine.open_dispatcher()
    except KeyboardInterrupt:
        logging.info("Trap receiver interrupted, shutting down")
    finally:
        snmp_engine.close_dispatcher()


if __name__ == "__main__":
    main()
