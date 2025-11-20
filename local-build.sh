#!/usr/bin/env bash
# local-build.sh - build (and optionally push) Docker image locally
#
# Usage:
#   ./local-build.sh [options]
#
# Options:
#   -t, --tag TAG         Image tag (default: local/snmpsim:latest)
#   -r, --registry REG    Registry prefix (e.g. myregistry.example.com/myorg)
#   -n, --no-cache        Pass --no-cache to docker build
#   -p, --push            Push image after successful build
#   -h, --help            Show this help
#
# Examples:
#   ./local-build.sh -t myimage:0.1
#   ./local-build.sh -r myregistry.local/lex -t snmpsim:1.2 -p

set -euo pipefail
 

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
DOCKERFILE="$SCRIPT_DIR/Dockerfile"
DEFAULT_TAG="local/snmpsim:latest"

TAG="${DEFAULT_TAG}"
REGISTRY=""
NO_CACHE=""
PUSH="false"

print_help() {
	sed -n '1,120p' "$0" | sed -n '1,60p'
}

while [[ $# -gt 0 ]]; do
	case "$1" in
		-t|--tag)
			TAG="$2"; shift 2;;
		-r|--registry)
			REGISTRY="$2"; shift 2;;
		-n|--no-cache)
			NO_CACHE="--no-cache"; shift;;
		-p|--push)
			PUSH="true"; shift;;
		-h|--help)
			print_help; exit 0;;
		--) shift; break;;
		-*) echo "Unknown option: $1" >&2; print_help; exit 1;;
		*) break;;
	esac
done

if [[ ! -f "$DOCKERFILE" ]]; then
	echo "Error: Dockerfile not found at $DOCKERFILE" >&2
	exit 2
fi

if [[ -n "$REGISTRY" ]]; then
	FULL_TAG="${REGISTRY%/}/${TAG}"
else
	FULL_TAG="$TAG"
fi

echo "Building image: $FULL_TAG"

# Enable BuildKit for faster builds and better output
export DOCKER_BUILDKIT=1

BUILD_CMD=(docker build -t "$FULL_TAG" $NO_CACHE -f "$DOCKERFILE" "$SCRIPT_DIR")

echo "Running: ${BUILD_CMD[*]}"
"${BUILD_CMD[@]}"

echo "Build succeeded: $FULL_TAG"

if [[ "$PUSH" == "true" ]]; then
	echo "Pushing $FULL_TAG"
	docker push "$FULL_TAG"
	echo "Push complete"
fi

exit 0
