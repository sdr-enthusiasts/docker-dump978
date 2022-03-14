# Declare the telegraf image so we can copy telegraf binary out of it,
# and avoid headache of having to add apt key / apt repo and/or build from src.
FROM telegraf AS telegraf
RUN touch /tmp/.nothing

# Build final image
FROM ghcr.io/sdr-enthusiasts/docker-baseimage:dump978-full

ENV PROMETHEUSPORT=9273 \
    PROMETHEUSPATH="/metrics" \
    ###########################################################################
    ##### AUTOGAIN ENVIRONMENT VARS #####
    # How often the autogain.sh is run (in seconds)
    AUTOGAIN_SERVICE_PERIOD=900 \
    # The autogain state file (init/finetune/finish)
    AUTOGAIN_STATE_FILE="/run/autogain/state" \
    # The current gain figure as-set by autogain
    AUTOGAIN_CURRENT_VALUE_FILE="/run/autogain/autogain_current_value" \
    # The timestamp (seconds since epoch) when the current gain figure was set
    AUTOGAIN_CURRENT_TIMESTAMP_FILE="/run/autogain/autogain_current_timestamp" \
    # The timestamp (seconds since epoch) when the current gain figure should be reviewed
    AUTOGAIN_REVIEW_TIMESTAMP_FILE="/run/autogain/autogain_review_timestamp" \
    # The maximum allowable percentage of strong messages
    AUTOGAIN_PERCENT_STRONG_MESSAGES_MAX=10.0 \
    # The minimum allowable percentage of strong messages
    AUTOGAIN_PERCENT_STRONG_MESSAGES_MIN=0.5 \
    # The number of seconds that autogain "init" stage should run for, for each gain level
    AUTOGAIN_INITIAL_PERIOD=7200 \
    # The minimum number of local_accepted messages that autogain "init" stage should run for, for each gain level
    AUTOGAIN_INITIAL_MSGS_ACCEPTED=1000000 \
    # The number of seconds that autogain "finetune" stage should run for, for each gain level
    AUTOGAIN_FINETUNE_PERIOD=604800 \
    # The minimum number of local_accepted messages that autogain "finetune" stage should run for, for each gain level
    AUTOGAIN_FINETUNE_MSGS_ACCEPTED=7000000 \
    # How long to run once finetune stage has finished before we start the process over (1 year)
    AUTOGAIN_FINISHED_PERIOD=31536000 \
    # Maximum gain level that autogain should use
    AUTOGAIN_MAX_GAIN_VALUE=49.6 \
    # Minimum gain level that autogain should use
    AUTOGAIN_MIN_GAIN_VALUE=0.0 \
    # State file that will disappear when the container is rebuilt/restarted - so autogain can detect container restart/rebuild
    AUTOGAIN_RUNNING_FILE="/tmp/.autogain_running" \
    # maximum accepted gain value
    AUTOGAIN_MAX_GAIN_VALUE_FILE="/run/autogain/autogain_max_value" \
    # minimum accepted gain value
    AUTOGAIN_MIN_GAIN_VALUE_FILE="/run/autogain/autogain_min_value" \
    # Current gain value
    GAIN_VALUE_FILE="/tmp/.gain_current"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Copy telegraf
COPY --from=telegraf /usr/bin/telegraf /usr/bin/telegraf

RUN set -x && \
    TEMP_PACKAGES=() && \
    KEPT_PACKAGES=() && \
    # Essentials
    TEMP_PACKAGES+=(build-essential) && \
    TEMP_PACKAGES+=(ca-certificates) && \
    TEMP_PACKAGES+=(cmake) && \
    TEMP_PACKAGES+=(curl) && \
    TEMP_PACKAGES+=(git) && \
    # Required for nicer logging.
    KEPT_PACKAGES+=(gawk) && \
    # uat2esnt dependencies (+ telegraf)
    KEPT_PACKAGES+=(socat) && \
    # healthcheck dependencies
    KEPT_PACKAGES+=(net-tools) && \
    KEPT_PACKAGES+=(jq) && \
    # Install packages.
    apt-get update && \
    apt-get install -y --no-install-recommends \
        ${KEPT_PACKAGES[@]} \
        ${TEMP_PACKAGES[@]} \
        && \
    git config --global advice.detachedHead false && \
    # Build & install uat2esnt
    git clone --branch=master --single-branch --depth=1 "https://github.com/adsbxchange/uat2esnt.git" "/src/uat2esnt" && \
    pushd "/src/uat2esnt" && \
    echo "uat2esnt $(git log | head -1)" >> /VERSIONS && \
    make all test && \
    cp -v ./uat2text /usr/local/bin/ && \
    cp -v ./uat2esnt /usr/local/bin/ && \
    cp -v ./uat2json /usr/local/bin/ && \
    cp -v ./extract_nexrad /usr/local/bin/ && \
    mkdir -p /run/uat2json && \
    popd && \
    mkdir -p /run/stats && \
    mkdir -p /run/autogain && \
    mkdir -p /etc/telegraf/telegraf.d && \
    # Clean up
    apt-get remove -y ${TEMP_PACKAGES[@]} && \
    apt-get autoremove -y && \
    rm -rf /src/* /tmp/* /var/lib/apt/lists/* && \
    # Write versions
    telegraf --version > /VERSIONS  && \
    ( dump978-fa --version > /VERSIONS 2>&1 || true ) && \
    grep dump978 /VERSIONS | cut -d ' ' -f2 >> /CONTAINER_VERSION && \
    # Print versions
    cat /VERSIONS && \
    cat /CONTAINER_VERSION

# Copy rootfs
COPY rootfs/ /

# Set s6 init as entrypoint
ENTRYPOINT [ "/init" ]

# Expose ports
EXPOSE 30978/tcp 30979/tcp 37981/tcp

# Add healthcheck - very long start period due to relatively small number of UAT aircraft
# May decrease start-period in future
HEALTHCHECK --timeout=60s --start-period=7200s --interval=600s CMD /scripts/healthcheck.sh

# TODO
#  - work out a way to test - maybe capture some output and parse it?
