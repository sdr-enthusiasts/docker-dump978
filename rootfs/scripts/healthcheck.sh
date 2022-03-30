#!/usr/bin/with-contenv bash
# shellcheck shell=bash

# Exit abnormally for any error
set -eo pipefail

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
    echo "dump978-fa not listening on port 30978, NOT OK."
    EXITCODE=1
else
    echo "dump978-fa listening on port 30978, OK."
fi

# Make sure dump978-fa is listening on port 30979
DUMP978_LISTENING_PORT_30979=""
REGEX_DUMP978_LISTENING_PORT_30979="^\s*tcp\s+\d+\s+\d+\s+(?>0\.0\.0\.0):30979\s+(?>0\.0\.0\.0):(?>\*)\s+LISTEN\s*$"
if echo "$NETSTAT_AN" | grep -P "$REGEX_DUMP978_LISTENING_PORT_30979" > /dev/null 2>&1; then
        DUMP978_LISTENING_PORT_30979="true"
fi
if [[ -z "$DUMP978_LISTENING_PORT_30979" ]]; then
    echo "dump978-fa not listening on port 30979, NOT OK."
    EXITCODE=1
else
    echo "dump978-fa listening on port 30979, OK."
fi

# Make sure socat/uat2esnt is listening on port 37981
SOCAT_LISTENING_PORT_37981=""
REGEX_SOCAT_LISTENING_PORT_37981="^\s*tcp\s+\d+\s+\d+\s+(?>0\.0\.0\.0):37981\s+(?>0\.0\.0\.0):(?>\*)\s+LISTEN\s*$"
if echo "$NETSTAT_AN" | grep -P "$REGEX_SOCAT_LISTENING_PORT_37981" > /dev/null 2>&1; then
        SOCAT_LISTENING_PORT_37981="true"
fi
if [[ -z "$SOCAT_LISTENING_PORT_37981" ]]; then
    echo "socat/uat2esnt not listening on port 37981, NOT OK."
    EXITCODE=1
else
    echo "socat/uat2esnt listening on port 37981, OK."
fi

# Make sure we're receiving messages from the SDR
returnvalue=$(jq .last_15min.total_raw_messages /run/stats/stats.json)
if [[ $(echo "$returnvalue > 0" | bc -l) -eq 1 ]]; then
    echo "last_15min:raw_accepted is $returnvalue: HEALTHY"
else
    echo "last_15min:raw_accepted is 0: UNHEALTHY"
    EXITCODE=1
fi

##### Service Death Counts #####
services=('autogain' 'dump978' 'stats' 'telegraf' 'telegraf_socat')
services+=('uat2esnt' 'uat2json' 'uat2json_rotate')
# For each service...
for service in "${services[@]}"; do
    # Get number of non-zero service exits
    returnvalue=$(s6-svdt \
                    -s "/run/s6/services/$service" | \
                    grep -cv 'exitcode 0')
    # Reset service death counts
    s6-svdt-clear "/run/s6/services/$service"
    # Log healthy/unhealthy and exit abnormally if unhealthy
    if [[ "$returnvalue" -eq "0" ]]; then
        echo "abnormal death count for service $service is $returnvalue: HEALTHY"
    else
        echo "abnormal death count for service $service is $returnvalue: UNHEALTHY"
        EXITCODE=1
    fi
done

# Exit with determined exit status
exit "$EXITCODE"
