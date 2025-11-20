#!/usr/bin/env bash
# local-run.sh - run the snmpsim container locally for development/testing
#
# Usage:
#   ./local-run.sh [options] -- [docker run extra args]
#
# Options:
#   -t, --tag TAG         Image tag to run (default: local/snmpsim:latest)
#   -n, --name NAME       Container name (default: snmpsim-local)
#   -p, --port HOST:CONTAINER
#                        Port mapping; can be provided multiple times
#                        (default: 1161:1161/udp 1162:1162/udp for SNMP/Traps)
#   -v, --volume HOST:CONTAINER
#                        Bind mount a host path into the container; may repeat
#   -d, --detach          Run container in background (detached)
#   -i, --interactive     Run container interactively (overrides -d)
#   -r, --remove          Remove container after exit (uses --rm)
#   -h, --help            Show this help
#
# Examples:
#   ./local-run.sh -t local/snmpsim:latest
#   ./local-run.sh -t local/snmpsim:latest -n my-snmpsim -p 1161:1161/udp -p 1162:1162/udp -d
#   ./local-run.sh -v $(pwd)/data:/data -t local/snmpsim:latest

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

DEFAULT_TAG="local/snmpsim:latest"
TAG="$DEFAULT_TAG"
NAME="snmpsim-local"
DETACH="false"
REMOVE="true"
INTERACTIVE="false"
PORT_ARGS=()
VOLUME_ARGS=()
EXTRA_DOCKER_ARGS=()

print_help() {
    sed -n '1,200p' "$0" | sed -n '1,120p'
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -t|--tag)
            TAG="$2"; shift 2;;
        -n|--name)
            NAME="$2"; shift 2;;
        -p|--port)
            PORT_ARGS+=("-p" "$2"); shift 2;;
        -v|--volume)
            VOLUME_ARGS+=("-v" "$2"); shift 2;;
        -d|--detach)
            DETACH="true"; shift;;
        -i|--interactive)
            INTERACTIVE="true"; shift;;
        -r|--remove)
            REMOVE="true"; shift;;
        -h|--help)
            print_help; exit 0;;
        --)
            shift; EXTRA_DOCKER_ARGS+=("$@"); break;;
        -*) echo "Unknown option: $1" >&2; print_help; exit 1;;
        *) EXTRA_DOCKER_ARGS+=("$1"); shift;;
    esac
done

# Default UDP port mappings commonly used by SNMP simulator
if [[ ${#PORT_ARGS[@]} -eq 0 ]]; then
    PORT_ARGS+=("-p" "161:161/udp")
    PORT_ARGS+=("-p" "162:162/udp")
fi

DOCKER_RUN=(docker run --name "$NAME")

if [[ "$REMOVE" == "true" ]]; then
    DOCKER_RUN+=(--rm)
fi

if [[ "$INTERACTIVE" == "true" ]]; then
    DOCKER_RUN+=(-it)
elif [[ "$DETACH" == "true" ]]; then
    DOCKER_RUN+=(-d)
fi

# Append port and volume args
DOCKER_RUN+=("${PORT_ARGS[@]}" "${VOLUME_ARGS[@]}")

# Default to showing container logs/attach behavior when not detached
DOCKER_RUN+=("$TAG")

echo "Running container from image: $TAG"
echo "Container name: $NAME"

echo "Command: ${DOCKER_RUN[*]} ${EXTRA_DOCKER_ARGS[*]}"

if [[ "$DETACH" == "true" ]]; then
    "${DOCKER_RUN[@]}" "${EXTRA_DOCKER_ARGS[@]}"
    echo "Container started (detached). Use: docker ps --filter name=$NAME"
    echo "To view logs: docker logs -f $NAME"
else
    # Run in foreground so user sees output; allow additional args
    "${DOCKER_RUN[@]}" "${EXTRA_DOCKER_ARGS[@]}"
fi

exit 0
