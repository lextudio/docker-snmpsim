# SNMP Simulator

This docker image starts up snmpsim.

The UDP port `161` should be mapped to the desired SNMP port.

By default this image contains an snmpwalk from `demo.snmplabs.com` under community name `demo`.

## Usage

To use your own snmpwalks you should mount a folder with snmpwalks like this:

    docker run -v /somewhere/with/snmpwalks:/usr/local/snmpsim/data \
               -p 161:161/udp \
               ghcr.io/lextudio/docker-snmpsim:master

The filename determines the SNMP community name.

If you want to run snmpsimd with more flags then you can use `EXTRA_FLAGS`, like this:

    docker run -v /somewhere/with/snmpwalks:/usr/local/snmpsim/data \
               -p 161:161/udp \
               -e EXTRA_FLAGS="--v3-user=testing --v3-auth-key=testing123"
               ghcr.io/lextudio/docker-snmpsim:master

To learn more about snmpsim, please visit [its docs](https://www.pysnmp.com/snmpsim/).

## Bug Reports

Issues about this image should be reported to https://github.com/lextudio/pysnmp/issues.
