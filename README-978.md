# Add 978

Follows this page: https://www.adsbexchange.com/how-to-feed/adding-978-mhz-ads-b-capability-to-your-pipi2/

Adds the capability based on the thebiggerguy/docker-ads-b

## Content block of Docker-compose.yml

```
  # dump978 ##################################################################
  dump978:
    image: thebiggerguy/docker-ads-b-dump1090:${TAG:-latest}
    build:
      context: dump978
      dockerfile: Dockerfile-dump978
      cache_from:
        - thebiggerguy/docker-ads-b-dump1090
        - thebiggerguy/docker-ads-b-dump1090:${TAG:-latest}
      args:
        DUMP1090_VERSION: git-9aea4f4
        DUMP1090_GIT_HASH: 9aea4f4a2a5acf07e3d428e365ae330676bed8b9
        DUMP1090_TAR_HASH: 5db0643be49a69148ef61abdd40acc9b633fac90a238dae5e18b95091bb983f4
    ports:
      - "30002:30002/tcp"
      - "30005:30005/tcp"
    devices:
      - "/dev/bus/usb/002/004"
    env_file:
      - variables-dump1090.env
    cap_add:
      - SYS_NICE
    restart: on-failure
```

## Content of variables-dump1090 (nothing for now, just a placeholder)

```
# variables-dump1090
```

## Content of dump978/Dockerfile-dump978

```
# Base Image ##################################################################
FROM multiarch/alpine:amd64-v3.9 as base

RUN cat /etc/apk/repositories && \
    echo '@edge http://nl.alpinelinux.org/alpine/edge/main' >> /etc/apk/repositories && \
    echo '@community http://nl.alpinelinux.org/alpine/edge/community' >> /etc/apk/repositories && \
    cat /etc/apk/repositories && \
    apk add --no-cache tini librtlsdr@edge libusb


# Builder Image ###############################################################
FROM base as builder

RUN apk update

RUN apk add --no-cache \
        curl ca-certificates \
        coreutils make gcc pkgconf \
        libc-dev librtlsdr-dev@edge libusb-dev

ARG DUMP1090_VERSION
ARG DUMP1090_GIT_HASH
ARG DUMP1090_TAR_HASH


RUN curl -L --output 'dump978-mutability.tar.gz' "https://github.com/mutability/dump978/archive/${DUMP1090_GIT_HASH}.tar.gz" && \
    sha256sum dump978-mutability.tar.gz && echo "${DUMP1090_TAR_HASH}  dump978-mutability.tar.gz" | sha256sum -c
RUN mkdir dump978 && cd dump978 && \
    tar -xvf ../dump978-mutability.tar.gz --strip-components=1
WORKDIR dump978
RUN make DUMP1090_VERSION="${DUMP1090_VERSION}"
RUN make test


# Final Image #################################################################
FROM base

COPY --from=builder /dump978/dump978 /usr/local/bin/dump978
COPY --from=builder /dump978/uat2esnt /usr/local/bin/uat2esnt
COPY launch_dump978.sh /usr/local/bin/launch_dump978.sh

RUN apk add rtl-sdr@edge

# Raw output
EXPOSE 30002/tcp
# Beast output
EXPOSE 30005/tcp

ENTRYPOINT ["tini", "--", "nice", "-n", "-5", "/bin/sh", "/usr/local/bin/launch_dump978.sh"]

# Metadata
ARG VCS_REF="Unknown"
LABEL maintainer="thebigguy.co.uk@gmail.com" \
      org.label-schema.name="Docker ADS-B - dump1090" \
      org.label-schema.description="Docker container for ADS-B - This is the dump1090 component" \
      org.label-schema.url="https://github.com/TheBiggerGuy/docker-ads-b" \
      org.label-schema.vcs-ref="${VCS_REF}" \
      org.label-schema.vcs-url="https://github.com/TheBiggerGuy/docker-ads-b" \
      org.label-schema.schema-version="1.0"
```

## Content of dump978/launch_dump978.sh

I could never get this work as an ENTRYPOINT line, so I created this tiny script to launch it. Note that you must chmod it to 755 or it won't launch inside the container. Also, note that adsb.lan is the FQDN of my primary ADS-B receiving Pi on my internal network. This solution rewrites 978 traffic (both direct and rebroadcast) as 1090-compatible traffic data and sends it over the network to where I have readsb running. You must allow readsb to accept traffic on port 30001.

```
#/bin/sh

/usr/bin/rtl_sdr -d 1 -f 978000000 -s 2083334 -g 48 - | /usr/local/bin/dump978 | /usr/local/bin/uat2esnt | /usr/bin/nc adsb.lan 30001
```
