FROM python:3.8-slim

RUN pip install snmpsim

ADD data /usr/local/snmpsim/data

EXPOSE 161/udp

CMD SNMPSIM_ALLOW_ROOT=true snmpsim-command-responder --agent-udpv4-endpoint=0.0.0.0:161 $EXTRA_FLAGS
