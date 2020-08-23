FROM debian:stable-slim

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN set -x && \
    apt-get update && \
    apt-get install --no-install-recommends -y \
        build-essential \
        ca-certificates \
        curl \
        git \
        libboost-dev \
        libboost-system1.67-dev \
        libboost-system1.67.0 \
        libboost-program-options1.67-dev \
        libboost-program-options1.67.0 \
        libboost-regex1.67-dev \
        libboost-regex1.67.0 \
        libboost-filesystem1.67-dev \
        libboost-filesystem1.67.0 \
        && \
    ## Build RTL-SDR
    curl -o - https://raw.githubusercontent.com/mikenye/deploy-rtl-sdr/master/deploy-rtl-sdr.sh | bash && \
    ## Build SoapySDR
    curl -o - https://raw.githubusercontent.com/mikenye/deploy-SoapySDR/master/deploy-SoapySDR.sh | bash && \
    ## Build dump978
    git clone https://github.com/flightaware/dump978.git /src/dump978 && \
    pushd /src/dump978 && \
    BRANCH_DUMP978="$(git tag --sort='-creatordate' | head -1)" && \
    git checkout "${BRANCH_DUMP978}" && \
    echo "dump978 ${BRANCH_DUMP978}" >> /VERSIONS && \
    make all && \
    make faup978 && \
    mkdir -p /usr/lib/piaware/helpers && \
    cp -v dump978-fa skyaware978 /usr/local/bin/ && \
    cp -v faup978 /usr/lib/piaware/helpers/ && \
    mkdir -p /usr/share/dump978-fa/html && \
    cp -a /src/dump978/skyaware/* /usr/share/dump978-fa/html/ && \
    ldconfig && \
    popd && \
    ## Clean up
    apt-get remove -y \
        build-essential \
        ca-certificates \
        curl \
        git \
        libboost-dev \
        libboost-system-dev \
        libboost-program-options-dev \
        libboost-regex-dev \
        libboost-filesystem-dev \
        && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/* /src

ENTRYPOINT [ "/usr/local/bin/dump978-fa" ]
