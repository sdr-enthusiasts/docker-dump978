#!/command/with-contenv bash
# shellcheck shell=bash

# Set default exit code
EXITCODE=0

# Get netstat output
NETSTAT_AN=$(netstat -an)

# Make sure dump978-fa is listening on port 30978
DUMP978_LISTENING_PORT_30978=""
REGEX_DUMP978_LISTENING_PORT_30978="^\s*tcp\s+\d+\s+\d+\s+(?>0\.0\.0\.0):30978\s+(?>0\.0\.0\.0):(?>\*)\s+LISTEN\s*$"
if echo "$NETSTAT_AN" | grep -P "$REGEX_DUMP978_LISTENING_PORT_30978" > /dev/null 2>&1; then
        DUMP978_LISTENING_PORT_30978="true"
fi
if [[ -z "$DUMP978_LISTENING_PORT_30978" ]]; then
    echo "[$(date)][UNHEALTHY] dump978-fa not listening on port 30978"
    EXITCODE=1
else
    echo "[$(date)][HEALTHY] dump978-fa listening on port 30978"
fi

# Make sure dump978-fa is listening on port 30979
DUMP978_LISTENING_PORT_30979=""
REGEX_DUMP978_LISTENING_PORT_30979="^\s*tcp\s+\d+\s+\d+\s+(?>0\.0\.0\.0):30979\s+(?>0\.0\.0\.0):(?>\*)\s+LISTEN\s*$"
if echo "$NETSTAT_AN" | grep -P "$REGEX_DUMP978_LISTENING_PORT_30979" > /dev/null 2>&1; then
        DUMP978_LISTENING_PORT_30979="true"
fi
if [[ -z "$DUMP978_LISTENING_PORT_30979" ]]; then
    echo "[$(date)][UNHEALTHY] dump978-fa not listening on port 30979"
    EXITCODE=1
else
    echo "[$(date)][HEALTHY] dump978-fa listening on port 30979"
fi

# Make sure socat/uat2esnt is listening on port 37981
SOCAT_LISTENING_PORT_37981=""
REGEX_SOCAT_LISTENING_PORT_37981="^\s*tcp\s+\d+\s+\d+\s+(?>0\.0\.0\.0):37981\s+(?>0\.0\.0\.0):(?>\*)\s+LISTEN\s*$"
if echo "$NETSTAT_AN" | grep -P "$REGEX_SOCAT_LISTENING_PORT_37981" > /dev/null 2>&1; then
        SOCAT_LISTENING_PORT_37981="true"
fi
if [[ -z "$SOCAT_LISTENING_PORT_37981" ]]; then
    echo "[$(date)][UNHEALTHY] socat/uat2esnt not listening on port 37981"
    EXITCODE=1
else
    echo "[$(date)][HEALTHY] socat/uat2esnt listening on port 37981"
fi

# Make sure we're receiving messages from the SDR
# get the number of messages received since process start:
mkdir -p /run/stats
if [[ -f /run/skyaware978/aircraft.json ]]; then
    read -r new_msg_count <<< "$(jq .messages /run/skyaware978/aircraft.json 2>/dev/null)"
else
    new_msg_count="STARTING"
fi
# get the number of messages previously read, or 0 if there's no history:
if [[ -f /run/stats/msgs_since_last_healthcheck ]]; then
    read -r old_msg_count < /run/stats/msgs_since_last_healthcheck
    secs_since_last_check="$(( $(date +%s) - $(stat -c '%Y' /run/stats/msgs_since_last_healthcheck) ))"
else
    old_msg_count=0
    secs_since_last_check="$(( $(date +%s) - $(stat -c '%Y' /run/service/skyaware978) ))"    # use skyaware978 modify time as the creation time of the container
fi
# Take conclusitions
if [[ "$new_msg_count" == "STARTING" ]]; then
    echo "[$(date)][STARTING] No messages have been received as the container is still starting"
    new_msg_count=0
elif (( new_msg_count < old_msg_count )) || (( old_msg_count == 0 && new_msg_count > 0 )); then
    echo "[$(date)][HEALTHY] $new_msg_count messages received since start of the SkyAware978 service ($secs_since_last_check secs ago)"
elif (( new_msg_count > old_msg_count )); then
    echo "[$(date)][HEALTHY] $(( new_msg_count - old_msg_count )) messages received since last HealthCheck ($secs_since_last_check secs ago)"
elif (( new_msg_count == old_msg_count )); then
    echo "[$(date)][UNHEALTHY] No messages received since last HealthCheck ($secs_since_last_check secs ago)"
    EXITCODE=1
else
    echo "[$(date)][ERROR] This situation cannot occur; new_msg_count=$new_msg_count; old_msg_count=$old_msg_count"
fi
echo "$new_msg_count" > /run/stats/msgs_since_last_healthcheck

##### Service Death Counts #####
# shellcheck disable=SC2046,SC2207
services=($(basename -a $(find /run/service/ -maxdepth 1 -type l)))
# For each service...
for service in "${services[@]}"; do
    abnormal_deaths="$(s6-svdt -s "/run/service/$service" | awk '/exitcode/ && !/exitcode 0/' | wc -l)"
    if (( abnormal_deaths > 0 )); then
        echo "[$(date)][UNHEALTHY] abnormal death count for service $service is $abnormal_deaths"
        EXITCODE=1
        # Reset service death counts
        s6-svdt-clear "/run/service/$service"
    else
        echo "[$(date)][HEALTHY] no abnormal death count for service $service"
    fi
done

# Exit with determined exit status
exit "$EXITCODE"
