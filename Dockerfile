# Declare the telegraf image so we can copy telegraf binary out of it,
# and avoid headache of having to add apt key / apt repo and/or build from src.
FROM telegraf AS telegraf
RUN touch /tmp/.nothing

# Build final image
FROM ghcr.io/sdr-enthusiasts/docker-baseimage:dump978-full

ENV PROMETHEUSPORT=9273 \
    PROMETHEUSPATH="/metrics"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Copy rootfs
COPY rootfs/ /

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
    mkdir -p /run/stats && \
    popd && \
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

# Set s6 init as entrypoint
ENTRYPOINT [ "/init" ]

# Expose ports
EXPOSE 30978/tcp 30979/tcp 37981/tcp

# Add healthcheck - very long start period due to relatively small number of UAT aircraft
# May decrease start-period in future
HEALTHCHECK --timeout=60s --start-period=7200s --interval=600s CMD /scripts/healthcheck.sh

# TODO
#  - work out a way to test - maybe capture some output and parse it?
