# DO NOT REMOVE THE ##telegraf## PREFIXES BELOW. THESE ARE USED BY GH ACTION deploy.yml
# TO AUTOMATICALLY BUILD IMAGES WITH AND WITHOUT TELEGRAF

# Declare the telegraf image so we can copy telegraf binary out of it,
# and avoid headache of having to add apt key / apt repo and/or build from src.

# hadolint ignore=DL3008,SC2086,SC2039,SC2068,DL3006
##telegraf##FROM telegraf AS telegraf
##telegraf##RUN touch /tmp/.nothing

# Declare the wreadsb image so we can copy readsb binary out of it,
# and avoid headache of having to add apt key / apt repo and/or build from src.
# hadolint ignore=DL3008,SC2086,SC2039,SC2068,DL3006
FROM ghcr.io/sdr-enthusiasts/docker-baseimage:wreadsb as wreadsb
RUN touch /tmp/.nothing

# Build final image
# hadolint ignore=DL3008,SC2086,SC2039,SC2068,DL3006
FROM ghcr.io/sdr-enthusiasts/docker-baseimage:dump978-full

ENV PROMETHEUSPORT=9273 \
    PROMETHEUSPATH="/metrics" \
    GAIN_VALUE_FILE="/var/globe_history/autogain/gain"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Copy telegraf
##telegraf##COPY --from=telegraf /usr/bin/telegraf /usr/bin/telegraf

# Copy wreadsb
COPY --from=wreadsb /usr/local/bin/readsb /usr/bin/readsb

# hadolint ignore=DL3008,SC2086,SC2039,SC2068
RUN set -x && \
    TEMP_PACKAGES=() && \
    KEPT_PACKAGES=() && \
    # Essentials
    TEMP_PACKAGES+=(ca-certificates) && \
    TEMP_PACKAGES+=(curl) && \
    # Required for nicer logging.
    KEPT_PACKAGES+=(gawk) && \
    ##telegraf##KEPT_PACKAGES+=(python3) && \
    # uat2esnt dependencies (+ telegraf)
    KEPT_PACKAGES+=(socat) && \
    # healthcheck dependencies
    KEPT_PACKAGES+=(net-tools) && \
    KEPT_PACKAGES+=(jq) && \
    KEPT_PACKAGES+=(lighttpd) && \
    KEPT_PACKAGES+=(lighttpd-mod-magnet) && \
    # wreadsb deps
    KEPT_PACKAGES+=(zlib1g) && \
    KEPT_PACKAGES+=(libzstd1) && \
    KEPT_PACKAGES+=(libncurses6) && \
    # Install packages.
    apt-get update && \
    apt-get install -y --no-install-recommends \
    ${KEPT_PACKAGES[@]} \
    ${TEMP_PACKAGES[@]} \
    && \
    # ensure lighttpd can bind to port 80
    setcap 'cap_net_bind_service=+ep' /usr/sbin/lighttpd && \
    # grab the bias t scripts
    curl -o /etc/s6-overlay/scripts/05-rtlsdr-biastee-init https://raw.githubusercontent.com/sdr-enthusiasts/sdre-bias-t-common/main/09-rtlsdr-biastee-init && \
    curl -o /etc/s6-overlay/scripts/05-rtlsdr-biastee-down https://raw.githubusercontent.com/sdr-enthusiasts/sdre-bias-t-common/main/09-rtlsdr-biastee-down && \
    chmod +x /etc/s6-overlay/scripts/05-rtlsdr-biastee-init && \
    chmod +x /etc/s6-overlay/scripts/05-rtlsdr-biastee-down && \
    mkdir -p /run/skyaware978 && \
    mkdir -p /run/stats && \
    mkdir -p /run/autogain && \
    ##telegraf##mkdir -p /etc/telegraf/telegraf.d && \
    # Health check
    mkdir -p /etc/lighttpd/lua && \
    echo -e 'server.modules += ("mod_magnet")\n\n$HTTP["url"] =~ "^/health/?" {\n  magnet.attract-physical-path-to = ("/etc/lighttpd/lua/healthcheck.lua")\n}' > /etc/lighttpd/conf-enabled/90-healthcheck.conf && \
    echo -e 'lighty.content = { "OK" }\nreturn 200' > /etc/lighttpd/lua/healthcheck.lua && \
    # Clean up
    apt-get remove -y ${TEMP_PACKAGES[@]} && \
    apt-get autoremove -y && \
    rm -rf /src/* /tmp/* /var/lib/apt/lists/* && \
    # Write versions
    ##telegraf##telegraf --version > /VERSIONS  && \
    ( dump978-fa --version > /VERSIONS 2>&1 || true ) && \
    IMAGE_VERSION=$(grep dump978 /VERSIONS | cut -d ' ' -f2) && \
    echo "${IMAGE_VERSION::7}" > /IMAGE_VERSION && \
    # Print versions
    cat /VERSIONS && \
    cat /IMAGE_VERSION

# Copy rootfs
COPY rootfs/ /

# Set s6 init as entrypoint
ENTRYPOINT [ "/init" ]

# Expose ports
EXPOSE 30978/tcp 30979/tcp 37981/tcp

# Add healthcheck
HEALTHCHECK --timeout=60s --start-period=7200s --interval=600s CMD /scripts/healthcheck.sh
