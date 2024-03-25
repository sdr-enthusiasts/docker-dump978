# sdr-enthusiasts/docker-dump978

- [sdr-enthusiasts/docker-dump978](#sdr-enthusiastsdocker-dump978)
  - [Introduction](#introduction)
  - [Ports](#ports)
  - [Paths \& Volumes](#paths--volumes)
  - [Up and Running - `docker run`](#up-and-running---docker-run)
  - [Up and Running - `docker-compose` (with `ultrafeeder`, `radarbox` and `piaware`)](#up-and-running---docker-compose-with-ultrafeeder-radarbox-and-piaware)
  - [Environment Variables](#environment-variables)
    - [Container Options](#container-options)
    - [`dump978-fa` General Options](#dump978-fa-general-options)
    - [`dump978-fa` RTL-SDR Options](#dump978-fa-rtl-sdr-options)
    - [General SDR Options](#general-sdr-options)
    - [InfluxDB Options](#influxdb-options)
    - [Prometheus Options](#prometheus-options)
    - [Autogain Options](#autogain-options)
  - [Autogain system](#autogain-system)
    - [Forcing autogain to re-run from scratch](#forcing-autogain-to-re-run-from-scratch)
    - [Container log messages while gain adjustments are made](#container-log-messages-while-gain-adjustments-are-made)
  - [`dump978` Web Pages](#dump978-web-pages)
  - [Logging](#logging)
  - [Getting help](#getting-help)

## Introduction

[![Docker Image Size (tag)](https://img.shields.io/docker/image-size/mikenye/dump978/latest)](https://hub.docker.com/r/mikenye/dump978)
[![Discord](https://img.shields.io/discord/734090820684349521)](https://discord.gg/sTf9uYF)

This container provides the FlightAware 978MHz UAT decoder dump978-fa and wiedehopf's implementation of `uat2esnt` code within `readsb`. (Thanks mutability for dump978-fa and the code used within readsb)

This container can be used alongside [sdr-enthusiasts/docker-readsb-protobuf](https://github.com/sdr-enthusiasts/docker-readsb-protobuf) to provide UAT into several feeders.

This container also contains InfluxData's [Telegraf](https://docs.influxdata.com/telegraf/), and can send flight data and `dump978` metrics to InfluxDB (if wanted - not started by default).

UAT is currently only used in the USA, so don't bother with this if you're not located in the USA.

NOTE: As of November 2, 2023, Telegraf support is only available in the container labeled `ghcr.io/sdr-enthusiasts/docker-dump978:telegraf`. It is no longer available in `ghcr.io/sdr-enthusiasts/docker-dump978:latest`. If you want to use Telegraf to send data to InfluxDB or Prometheus, please switch to the `:telegraf` label.

## Ports

The container listens on the following TCP ports:

| Port    | Description                                                                                                                                                |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `30978` | Raw UAT output (compatible with wiedehopf readsb's `uat_in`, but NOT compatible with `readsb`'s `raw_in`!)                                                 |
| `30979` | Decoded JSON output                                                                                                                                        |
| `37981` | `uat2esnt/readsb` converted raw output. This IS compatible with `readsb`'s `raw_in`. (DEPRECATED, use `uat_in` on port 30978 or `beast_in` on port 37982!) |
| `37982` | `uat2esnt/readsb` converted beast output. This IS compatible with `readsb`'s `beast_in`.                                                                   |
| `80`    | Webserver for SkyAware978 and HTTP HealthCheck                                                                                                             |

## Paths & Volumes

| Path (inside container) | Details |
|-------------------------|---------|
| `/var/globe_history` | Map this to persistant storage if you set `DUMP978_SDR_GAIN=autogain` |

## Up and Running - `docker run`

```bash
docker run \
    -d \
    --restart=always \
    -it \
    --name dump978 \
    -p 30978:30978 \
    -p 30979:30979 \
    -p 30980:80 \
    -p 37981:37981 \
    -p 37982:37982 \
    --device /dev/bus/usb:/dev/bus/usb \
    -e DUMP978_RTLSDR_DEVICE=00000978 \
    ghcr.io/sdr-enthusiasts/docker-dump978:latest
```

You can now:

- Add a net-connector to your readsb container, to pull data from port 37982 as `beast_in`, eg: `<DOCKERHOST>,37982,beast_in`
- Add the following environment variables to your piaware container:

```yaml
- UAT_RECEIVER_TYPE=relay
- UAT_RECEIVER_HOST=<DOCKERHOST>
```

You should now be feeding UAT to most aggregators.

## Up and Running - `docker-compose` (with `ultrafeeder`, `radarbox` and `piaware`)

Here is an example `docker-compose.yml`:

<details>
  <summary>&lt;&dash;&dash; Click the arrow to see the <code>docker-compose.yml</code> text</summary>

```yaml
  dump978:
# dump978 gets UAT data from the SDR
    image: ghcr.io/sdr-enthusiasts/docker-dump978:latest
#    profiles:
#      - donotstart
    tty: true
    container_name: dump978
    hostname: dump978
    restart: always
    labels:
      - "autoheal=true"
    device_cgroup_rules:
      - 'c 189:* rwm'
    environment:
      - TZ=${FEEDER_TZ}
      - LAT=${FEEDER_LAT}
      - LON=${FEEDER_LONG}
      - DUMP978_RTLSDR_DEVICE=${UAT_SDR_SERIAL}
      - DUMP978_SDR_GAIN=${UAT_SDR_GAIN}
      - DUMP978_SDR_PPM=${UAT_SDR_PPM}
    volumes:
      - /opt/adsb/dump978:/var/globe_history
      - /dev:/dev:ro
    tmpfs:
      - /run:exec,size=64M
      - /tmp:size=64M
      - /var/log:size=32M

ultrafeeder:
  image: ghcr.io/sdr-enthusiasts/docker-adsb-ultrafeeder
  tty: true
  container_name: ultrafeeder
  hostname: ultrafeeder
  restart: unless-stopped
  device_cgroup_rules:
    - "c 189:* rwm"
  ports:
    - 8080:80 # to expose the web interface
    - 9273-9274:9273-9274 # to expose the statistics interface to Prometheus
  environment:
    # --------------------------------------------------
    # general parameters:
    - LOGLEVEL=error
    - TZ=${FEEDER_TZ}
    # --------------------------------------------------
    # SDR related parameters:
    - READSB_DEVICE_TYPE=rtlsdr
    - READSB_RTLSDR_DEVICE=${ADSB_SDR_SERIAL}
    - READSB_RTLSDR_PPM=${ADSB_SDR_PPM}
    #
    # --------------------------------------------------
    # readsb/decoder parameters:
    - READSB_LAT=${FEEDER_LAT}
    - READSB_LON=${FEEDER_LONG}
    - READSB_ALT=${FEEDER_ALT_M}m
    - READSB_GAIN=${ADSB_SDR_GAIN}
    - READSB_MODEAC=true
    - READSB_RX_LOCATION_ACCURACY=2
    - READSB_STATS_RANGE=true
    #
    # --------------------------------------------------
    # Sources and Aggregator connections:
    # (Note - remove the ones you are not using / feeding)
    - ULTRAFEEDER_CONFIG=
      adsb,dump978,30978,uat_in;
      adsb,feed.adsb.fi,30004,beast_reduce_plus_out;
      adsb,in.adsb.lol,30004,beast_reduce_plus_out;
      adsb,feed.adsb.one,64004,beast_reduce_plus_out;
      adsb,feed.planespotters.net,30004,beast_reduce_plus_out;
      adsb,feed.theairtraffic.com,30004,beast_reduce_plus_out;
      mlat,feed.adsb.fi,31090,39000;
      mlat,in.adsb.lol,31090,39001;
      mlat,feed.adsb.one,64006,39002;
      mlat,mlat.planespotters.net,31090,39003;
      mlat,feed.theairtraffic.com,31090,39004;
      mlathub,piaware,30105,beast_in;
      mlathub,rbfeeder,30105,beast_in;
      mlathub,radarvirtuel,30105,beast_in
    # If you really want to feed ADSBExchange, you can do so by adding this above:
    #        adsb,feed1.adsbexchange.com,30004,beast_reduce_plus_out,uuid=${ADSBX_UUID};
    #        mlat,feed.adsbexchange.com,31090,39005,uuid=${ADSBX_UUID}
    #
    # --------------------------------------------------
    - UUID=${MULTIFEEDER_UUID}
    - MLAT_USER=${FEEDER_NAME}
    #
    # --------------------------------------------------
    # TAR1090 (Map Web Page) parameters:
    - UPDATE_TAR1090=true
    - TAR1090_DEFAULTCENTERLAT=${FEEDER_LAT}
    - TAR1090_DEFAULTCENTERLON=${FEEDER_LONG}
    - TAR1090_MESSAGERATEINTITLE=true
    - TAR1090_PAGETITLE=${FEEDER_NAME}
    - TAR1090_PLANECOUNTINTITLE=true
    - TAR1090_ENABLE_AC_DB=true
    - TAR1090_FLIGHTAWARELINKS=true
    - HEYWHATSTHAT_PANORAMA_ID=${FEEDER_HEYWHATSTHAT_ID}
    - HEYWHATSTHAT_ALTS=${FEEDER_HEYWHATSTHAT_ALTS}
    - TAR1090_SITESHOW=true
    - TAR1090_RANGE_OUTLINE_COLORED_BY_ALTITUDE=true
    - TAR1090_RANGE_OUTLINE_WIDTH=2.0
    - TAR1090_RANGERINGSDISTANCES=50,100,150,200
    - TAR1090_RANGERINGSCOLORS='#1A237E','#0D47A1','#42A5F5','#64B5F6'
    - TAR1090_USEROUTEAPI=true
    #
    # --------------------------------------------------
    # GRAPHS1090 (Decoder and System Status Web Page) parameters:
    # The two 978 related parameters should only be included if you are running dump978 for UAT reception (USA only)
    - GRAPHS1090_DARKMODE=true
    - URL_978=http://dump978/skyaware978
  volumes:
    - /opt/adsb/ultrafeeder/globe_history:/var/globe_history
    - /opt/adsb/ultrafeeder/graphs1090:/var/lib/collectd
    - /proc/diskstats:/proc/diskstats:ro
    - /dev:/dev:ro
  tmpfs:
    - /run:exec,size=256M
    - /tmp:size=128M
    - /var/log:size=32M

piaware:
  # piaware feeds ADS-B and UAT data (from ultrafeeder) to FlightAware. It also includes a GUI Radar website and a status website
  # If you're not capturing UAT data with the dump978 container, remove or comment out the UAT_RECEIVER_TYPE and UAT_RECEIVER_HOST lines in the environment section below.
  image: ghcr.io/sdr-enthusiasts/docker-piaware
  # profiles:
  #   - donotstart
  tty: true
  container_name: piaware
  hostname: piaware
  restart: always
  labels:
    - "autoheal=true"
  ports:
    - 8081:8080
    - 8088:80
  environment:
    - BEASTHOST=ultrafeeder
    - LAT=${FEEDER_LAT}
    - LONG=${FEEDER_LONG}
    - TZ=${FEEDER_TZ}
    - FEEDER_ID=${PIAWARE_FEEDER_ID}
    - UAT_RECEIVER_TYPE=relay
    - UAT_RECEIVER_HOST=dump978
  tmpfs:
    - /run:exec,size=64M
    - /var/log

rbfeeder:
  # rbfeeder feeds ADS-B and UAT data (from ultrafeeder) to RadarBox.
  # If you're not capturing UAT data with the dump978 container, remove or comment out the UAT_RECEIVER_HOST line in the environment section below.
  image: ghcr.io/sdr-enthusiasts/docker-radarbox
  # profiles:
  #   - donotstart
  tty: true
  container_name: rbfeeder
  hostname: rbfeeder
  restart: always
  labels:
    - "autoheal=true"
  environment:
    - BEASTHOST=ultrafeeder
    - UAT_RECEIVER_HOST=dump978
    - LAT=${FEEDER_LAT}
    - LONG=${FEEDER_LONG}
    - ALT=${FEEDER_ALT_M}
    - TZ=${FEEDER_TZ}
    - SHARING_KEY=${RADARBOX_SHARING_KEY}
  tmpfs:
    - /run:exec,size=64M
    - /var/log
```

</details>

You should now be feeding ADSB-ES & UAT to the "new" aggregators, FlightAware, and Radarbox.

## Environment Variables

### Container Options

| Variable | Description                                                                                                                                 | Default |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| `TZ`     | Local timezone in ["TZ database name" format](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).                                | `UTC`   |
| `LAT`    | Latitude of your receiver. Only required if you want range statistics for InfluxDB, Prometheus, or tar1090/ultrafeeder graphs. | Unset   |
| `LON`    | Longitude of your receiver. Only required if you want range statistics for InfluxDB, Prometheus, or tar1090/ultrafeeder graphs. | Unset   |
| `DUMP978_MSG_MONITOR_INTERVAL` | Interval between runs of the Message Monitor that checks if new messages are received. Format of value is anything that is accepted by the Linux `sleep` command | Unset (30 minutes) |
| `DUMP978_MSG_MONITOR_RESTART_WHEN_STALE` | If set to `true`/`on`/`yes`/`1`, the receiver process is restarted when no messages are received during the monitoring interval | `true` |

### `dump978-fa` General Options

Where the default value is "Unset", `dump978-fa`'s default will be used.

| Variable | Description | Controls which `dump978-fa` option | Default |
|----------|-------------|--------------------------------|---------|
| `DUMP978_DEVICE_TYPE` | Currently only `rtlsdr` is supported. If you have another type of radio, please open an issue and I'll try to get it added. | `--sdr driver=` | `rtlsdr` |
| `DUMP978_SDR_AGC` | Set to any value to enable SDR AGC. | `--sdr-auto-gain` | Unset |
| `DUMP978_SDR_GAIN` | Set gain (in dB). Use autogain to have the container determine an appropriate gain, more on this below. | `--sdr-gain` | Unset |
| `DUMP978_SDR_PPM` | Set SDR frequency correction in PPM. | `--sdr-ppm` | Unset |
| `DUMP978_JSON_STDOUT` | Write decoded json to the container log. Useful for troubleshooting, but don't leave enabled! | `--json-stdout` | Unset |

### `dump978-fa` RTL-SDR Options

Use with `DUMP978_DEVICE_TYPE=rtlsdr`.

Where the default value is "Unset", `dump978-fa`'s default will be used.

| Variable                | Description                              | Controls which `dump978-fa` option | Default |
| ----------------------- | ---------------------------------------- | ---------------------------------- | ------- |
| `DUMP978_RTLSDR_DEVICE` | If using Select device by serial number. | `--sdr driver=rtlsdr,serial=`      | Unset   |

### General SDR Options

| Variable                 | Description                                          | Default |
| ------------------------ | ---------------------------------------------------- | ------- |
| `DUMP978_ENABLE_BIASTEE` | Set to any value to enable bias-tee on your RTL-SDR. | Unset   |

### InfluxDB Options

NOTE: As of November 2, 2023, Telegraf support is only available in the container labeled `ghcr.io/sdr-enthusiasts/docker-dump978:telegraf`. It is no longer available in `ghcr.io/sdr-enthusiasts/docker-dump978:latest`. If you want to use Telegraf to send data to InfluxDB or Prometheus, please switch to the `:telegraf` label.

These variables control the sending of flight data and dump978 metrics to [InfluxDB](https://docs.influxdata.com/influxdb/) (via a built-in instance of [Telegraf](https://docs.influxdata.com/telegraf/)).

| Variable                 | Description                                                                                                                             | Default |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| `INFLUXDBURL`            | The full HTTP URL for your InfluxDB instance. Required for both InfluxDB v1 and v2.                                                     | Unset   |
| `INFLUXDBUSERNAME`       | If using authentication, a username for your InfluxDB instance. If not using authentication, leave unset. Not required for InfluxDB v2. | Unset   |
| `INFLUXDBPASSWORD`       | If using authentication, a password for your InfluxDB instance. If not using authentication, leave unset. Not required for InfluxDB v2. | Unset   |
| `INFLUXDB_V2`            | Set to a non empty value to enable InfluxDB V2 output.                                                                                  | Unset   |
| `INFLUXDB_V2_BUCKET`     | Required if `INFLUXDB_V2` is set, bucket must already exist in your InfluxDB v2 instance.                                               | Unset   |
| `INFLUXDB_V2_ORG`        | Required if `INFLUXDB_V2` is set.                                                                                                       | Unset   |
| `INFLUXDB_V2_TOKEN`      | Required if `INFLUXDB_V2` is set.                                                                                                       | Unset   |
| `INFLUXDB_SKIP_AIRCRAFT` | Set to any value to skip publishing aircraft data to InfluxDB to minimize bandwidth and database size.                                  | Unset   |

### Prometheus Options

NOTE: As of November 2, 2023, Telegraf support is only available in the container labeled `ghcr.io/sdr-enthusiasts/docker-dump978:telegraf`. It is no longer available in `ghcr.io/sdr-enthusiasts/docker-dump978:latest`. If you want to use Telegraf to send data to InfluxDB or Prometheus, please switch to the `:telegraf` label.

These variables control exposing flight data to [Prometheus](https://prometheus.io) (via a built-in instance of [Telegraf](https://docs.influxdata.com/telegraf/)).

| Variable            | Description                                                 | Default    |
| ------------------- | ----------------------------------------------------------- | ---------- |
| `ENABLE_PROMETHEUS` | Set to any string to enable Prometheus support              | Unset      |
| `PROMETHEUSPORT`    | The port that the prometheus client will listen on          | `9273`     |
| `PROMETHEUSPATH`    | The path that the prometheus client will publish metrics on | `/metrics` |

### Autogain Options

These variables control the autogain system (explained further below). These should rarely need changing from the defaults.

| Variable | Description | Default |
|----------|-------------|---------|
| `DUMP978_AUTOGAIN_INITIAL_TIMEPERIOD` | How long the autogain initialization phase should take (ie: "roughing in"), in seconds. | `21600` (6 hours) |
| `DUMP978_AUTOGAIN_INITIAL_INTERVAL` | How often autogain should measure and adjust the gain during the initialization phase, in seconds. | `600` (10 minutes) |
| `DUMP978_AUTOGAIN_SUBSEQUENT_INTERVAL` | How often autogain should measure and adjust the gain after the initialization phase is done, in seconds. | `84600` (24 hours) |
| `DUMP978_AUTOGAIN_ADJUSTMENT_LIMITS` | If set to `true`/`on`/`yes`/`1`, while in the initialization phase, autogain will only adjust the gain during the timeframe set by the `DUMP978_AUTOGAIN_ADJUSTMENT_TIMEFRAME` parameter. | `true` |
| `DUMP978_AUTOGAIN_ADJUSTMENT_TIMEFRAME` | Timeframe limits for autogain during the initializaion phase, in `HHMM-HHMM` (start hours/minutes to end hours/minutes). If an adjustment "run" falls outside these limits, the autogain adjustment is delayed until the start of the next timeframe. Times are based on the container's Timezone (`TZ`) setting. | `0900-1800` (9 AM - 6 PM, local container time) |
| `DUMP978_AUTOGAIN_LOW_PCT` | If the percentage of "strong signals" (>3dB) over a measuring period is less than this parameter, the gain will be increased by 1 position | `2.5` (2.5%) |
| `DUMP978_AUTOGAIN_HIGH_PCT` | If the percentage of "strong signals" (>3dB) over a measuring period is more than this parameter, the gain will be decreased by 1 position | `6.0` (6.0%) |
| `READSB_AUTOGAIN_MIN_SAMPLES` | Minimum number of received samples for autogain to be able to consider adjusting the gain | `1000` |
| `READSB_AUTOGAIN_USE_RAW` |  If set to `true`/`on`/`yes`/`1`, the autogain function will use the "raw" message count rather than the "accepted" message count. | `true` |
| `SUBSEQUENT_INTERVAL_MINIMUM_COMPLETION_PCT` | Minimum percentage of `DUMP978_AUTOGAIN_SUBSEQUENT_INTERVAL` time that needs to be completed before autogain will use the collected data during the subsequent/long-term process | `50` |

## Autogain system

An automatic gain adjustment system is included in this container, and can be activated by setting the environment variable `DUMP978_SDR_GAIN` to `autogain`. You should also map `/var/globe_history/` to persistent storage, otherwise the autogain system will start over each time the container is restarted.

Autogain will take several hours to initially work out a reasonable gain. This is the so-called "initialization period", which is by default 6 hours. It will then perform a daily measurement to see if your gain needs further adjusting.

The autogain system will work as follows; values are based on the default parameter settings from above:

1. `dump978` is set to maximum gain.
2. Initial results are collected every 10 minutes, for up to 6 hours (initialization phase). If `DUMP978_AUTOGAIN_ADJUSTMENT_LIMITS` is set to true, measurements are suspended if the time is outside the set time limits (0900 - 1800 local container time). Every 10 minutes, the gain is adjusted by 1 position if the average percentage of "strong" signals (>-3dB) is less than 2.5% or more than 6.0%.
3. After the initialization phase is over, the average percentage of "strong signal" is calculated on a daily basis, and an adjustment is made accordingly.

### Forcing autogain to re-run from scratch

Run `docker exec dump978 autogain978 reset` to remove reset all autogain data and start the initialization phase fron scratch

### Container log messages while gain adjustments are made

When a gain adjustment is made, `dump978-fa` and related processes are forcibly restarted. This will cause a number of messages to the container logs showing that these processes are terminated, and subsequently restarted. These messages are normal during an autogain gain adjustment, and are not errors in the container.

## `dump978` Web Pages

The container's webserver makes SkyAware978 (and the related `data` directories with `json` statistics files) available at `/skyaware978`. This means, using the port mapping example shown above, that you can access these URLs (among other things):

- [http://my_ip:30980/skyaware978](http://my_ip:30980/skyaware978) -- SkyAware978 map
- [http://my_ip:30980/skyaware978/data/aircraft.json](http://my_ip:30980/skyaware978/data/aircraft.json) -- aircraft.json statistics file
- [http://my_ip:30980/health](http://my_ip:30980/health) -- HealthCheck results (returns `OK` if container is healthy)

## Logging

- All processes are logged to the container's stdout, and can be viewed with `docker logs [-f] container`.

## Getting help

Please feel free to [open an issue on the project's GitHub](https://github.com/sdr-enthusiasts/docker-dump978/issues).

I also have a [Discord channel](https://discord.gg/sTf9uYF), feel free to [join](https://discord.gg/sTf9uYF) and converse.
