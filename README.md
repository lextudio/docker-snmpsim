# SNMP Simulator

This docker image starts up snmpsim and now bundles a PySNMP-based trap/inform
monitor inspired by `snmpreceiver/snmptrapd.py`.

Map the UDP ports `161` (agent) **and** `162` (trap receiver) to the desired host
ports.

By default this image contains an snmpwalk from `demo.snmplabs.com` under community name `demo`.

## Usage

To use your own snmpwalks you should mount a folder with snmpwalks like this:

    docker run -v /somewhere/with/snmpwalks:/usr/local/snmpsim/data \
               -p 161:161/udp -p 162:162/udp \
               ghcr.io/lextudio/docker-snmpsim:master

The filename determines the SNMP community name.

If you want to run snmpsimd with more flags then you can use `EXTRA_FLAGS`, like this:

    docker run -v /somewhere/with/snmpwalks:/usr/local/snmpsim/data \
               -p 161:161/udp -p 162:162/udp \
               -e EXTRA_FLAGS="--v3-user=testing --v3-auth-key=testing123" \
               ghcr.io/lextudio/docker-snmpsim:master

### Trap / Inform monitor controls

The `SNMPTRAPD_ENABLED` environment variable (defaults to `1`) toggles the trap
listener. Set it to `0` or `false` to disable the helper if you only need the
agent.

The helper respects additional optional variables:

* `SNMPTRAPD_ADDRESS` / `SNMPTRAPD_PORT` – override the bind address/port (defaults `0.0.0.0:162`).
* `SNMPTRAPD_COMMUNITY` – change the community string used for accepting traps (`public` by default).
* `SNMPTRAPD_LOG_FILE` – write trap logs to a file instead of stdout.
* `SNMPTRAPD_LOG_LEVEL` – change log verbosity (e.g. `DEBUG`, `INFO`, ...).
* `SNMPTRAPD_V3_USERS` – semicolon-separated list of SNMPv3 users in the form
  `user:authProto:authKey:privProto:privKey` (multiple users can be chained with `;`). Example:

  ```shell
  -e SNMPTRAPD_V3_USERS="tester:SHA:authpass1:AES128:privpass1;observer:MD5:authpass2:NONE:"
  ```

  Supported auth protocols: `MD5`, `SHA`, `SHA224`, `SHA256`, `SHA384`, `SHA512`, or `NONE`.
  Supported privacy protocols: `DES`, `3DES`, `AES128`, `AES192`, `AES256`, or `NONE`.

To learn more about snmpsim, please visit [its docs](https://www.pysnmp.com/snmpsim/).

## Bug Reports

Issues about this image should be reported to https://github.com/lextudio/pysnmp/issues.
