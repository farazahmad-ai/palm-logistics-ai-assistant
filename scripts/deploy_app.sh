#!/usr/bin/env bash

# Deploy one exact Palm Logistics commit on the EC2 application server.
# Run as root (GitHub Actions invokes it through AWS Systems Manager).

set -Eeuo pipefail

COMMIT_SHA="${1:-}"
APP_USER="palmapp"
APP_ROOT="/opt/palm-logistics"
REPOSITORY_DIR="${APP_ROOT}/repository"
SERVICE_NAME="palm-logistics"
HEALTH_URL="http://127.0.0.1:8501/_stcore/health"
ENVIRONMENT_FILE="/etc/palm-logistics/palm-logistics.env"

if [[ ! "${COMMIT_SHA}" =~ ^[0-9a-f]{40}$ ]]; then
    echo "Usage: $0 <40-character-git-commit-sha>" >&2
    exit 2
fi

if [[ ! -d "${REPOSITORY_DIR}/.git" ]]; then
    echo "Git repository not found at ${REPOSITORY_DIR}. Complete the EC2 bootstrap first." >&2
    exit 3
fi

previous_commit="$(runuser -u "${APP_USER}" -- git -C "${REPOSITORY_DIR}" rev-parse HEAD)"

wait_for_health() {
    for attempt in {1..30}; do
        if curl --fail --silent --show-error "${HEALTH_URL}" >/dev/null; then
            return 0
        fi
        sleep 2
    done
    return 1
}

run_smoke_test() {
    runuser -u "${APP_USER}" -- env \
        HOME="/var/lib/palm-logistics" \
        PALM_ENV_FILE="${ENVIRONMENT_FILE}" \
        /usr/local/bin/uv run --frozen --project "${REPOSITORY_DIR}" \
        python "${REPOSITORY_DIR}/scripts/deployment_smoke_test.py"
}

rollback() {
    local exit_code="${1:-1}"
    local rollback_failed=0
    trap - ERR INT TERM
    set +e
    echo "Deployment failed. Rolling back to ${previous_commit}." >&2
    runuser -u "${APP_USER}" -- git -C "${REPOSITORY_DIR}" \
        checkout --detach "${previous_commit}" || rollback_failed=1
    runuser -u "${APP_USER}" -- env HOME="/var/lib/palm-logistics" \
        /usr/local/bin/uv sync --frozen --project "${REPOSITORY_DIR}" || rollback_failed=1
    systemctl restart "${SERVICE_NAME}" || rollback_failed=1

    if ! wait_for_health; then
        echo "CRITICAL: rollback process health check failed." >&2
        rollback_failed=1
    elif ! run_smoke_test; then
        echo "CRITICAL: rollback dependency smoke test failed." >&2
        rollback_failed=1
    fi

    if (( rollback_failed == 0 )); then
        echo "Rollback checks passed for ${previous_commit}." >&2
    else
        echo "CRITICAL: rollback did not restore a verified healthy release." >&2
    fi
    exit "${exit_code}"
}

echo "Fetching commit ${COMMIT_SHA}."
runuser -u "${APP_USER}" -- git -C "${REPOSITORY_DIR}" fetch --prune origin
runuser -u "${APP_USER}" -- git -C "${REPOSITORY_DIR}" cat-file -e "${COMMIT_SHA}^{commit}"

# Fetching and validating a commit do not change the running release. Enable
# rollback only immediately before the working tree is changed.
trap 'rollback $?' ERR
trap 'rollback 130' INT
trap 'rollback 143' TERM
runuser -u "${APP_USER}" -- git -C "${REPOSITORY_DIR}" checkout --detach "${COMMIT_SHA}"

echo "Synchronizing the environment from uv.lock."
runuser -u "${APP_USER}" -- env HOME="/var/lib/palm-logistics" \
    /usr/local/bin/uv sync --frozen --project "${REPOSITORY_DIR}"

echo "Restarting ${SERVICE_NAME}."
systemctl restart "${SERVICE_NAME}"

if ! wait_for_health; then
    echo "Streamlit process health check failed after 60 seconds." >&2
    false
fi
echo "Streamlit process health check passed."

echo "Running production dependency smoke tests."
run_smoke_test

echo "Deployment succeeded: ${COMMIT_SHA}."
trap - ERR INT TERM
