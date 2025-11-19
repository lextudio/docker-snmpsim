FROM python:3.10-slim

# Metadata
LABEL maintainer="support@lextudio.com"
LABEL description="Docker image for running snmpsim (PySNMP Simulator)"
LABEL version="1.1"

RUN pip install --no-cache-dir cryptography pysnmp snmpsim

COPY data /usr/local/snmpsim/data
COPY snmptrapd.py /opt/snmptrapd.py
COPY start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 161/udp
EXPOSE 162/udp

ENV SNMPTRAPD_ENABLED=1

ENTRYPOINT ["/start.sh"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s \
  CMD sh -c 'SNMPSIM_PID=$(cat /var/run/snmpsim/snmpsim.pid 2>/dev/null) && kill -0 "$SNMPSIM_PID" 2>/dev/null || exit 1; FLAG="${SNMPTRAPD_ENABLED:-1}"; if [ "$FLAG" = "0" ] || [ "$FLAG" = "false" ]; then exit 0; fi; TRAP_PID=$(cat /var/run/snmpsim/snmptrapd.pid 2>/dev/null) && kill -0 "$TRAP_PID" 2>/dev/null || exit 1'
