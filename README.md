# mikenye/dump978

[![GitHub Workflow Status](https://img.shields.io/github/workflow/status/mikenye/docker-dump978/Deploy%20to%20Docker%20Hub)](https://github.com/mikenye/docker-dump978/actions?query=workflow%3A%22Deploy+to+Docker+Hub%22)
[![Docker Pulls](https://img.shields.io/docker/pulls/mikenye/dump978.svg)](https://hub.docker.com/r/mikenye/dump978)
[![Docker Image Size (tag)](https://img.shields.io/docker/image-size/mikenye/dump978/latest)](https://hub.docker.com/r/mikenye/dump978)
[![Discord](https://img.shields.io/discord/734090820684349521)](https://discord.gg/sTf9uYF)

This container provides the FlightAware 978MHz UAT decoder, and the ADSBExchange fork of `uat2esnt`, working together in harmony. A rare example of harmony in these turblent times. :-)

This container can be used alongside [mikenye/readsb-protobuf](https://github.com/mikenye/docker-readsb-protobuf) to provide UAT into several feeders.

This container also contains InfluxData's [Telegraf](https://docs.influxdata.com/telegraf/), and can send flight data and `dump978` metrics to InfluxDB (if wanted - not started by default).

UAT is currently only used in the USA, so don't bother with this if you're not located in the USA.

## Ports

The container listens on the following TCP ports:

| Port | Description |
|------|-------------|
| `30978` | Raw UAT output (NOT compatible with `readsb`'s `raw_in`!) |
| `30979` | Decoded JSON output |
| `37981` | `uat2esnt` converted output. This IS compatible with `readsb`'s `raw_in`. |

## Up and Running - `docker run`

```bash
docker run \
    -d \
    --restart=always \
    -it \
    --name dump978 \
    -p 30978:30978 \
    -p 30979:30979 \
    -p 37981:37981 \
    --device /dev/bus/usb:/dev/bus/usb \
    -e DUMP978_RTLSDR_DEVICE=00000978 \
    mikenye/dump978
```

You can now:

* Add a net-connector to your readsb container, to pull data from port 37981 as `raw_in`, eg: `<DOCKERHOST>,37981,raw_in`
* Add the following environment variables to your piaware container:
  * `UAT_RECEIVER_TYPE=relay`
  * `UAT_RECEIVER_HOST=<DOCKERHOST>`

You should now be feeding UAT to ADSBExchange and FlightAware.

## Up and Running - `docker-compose` (with `readsb`, `adsbx` and `piaware`)

Here is an example `docker-compose.yml`:

```yaml
version: '3.8'

volumes:
  readsbpb_rrd:
  readsbpb_autogain:

services:
  readsb:
    image: mikenye/readsb-protobuf
    tty: true
    container_name: readsb
    restart: always
    devices:
      - /dev/bus/usb:/dev/bus/usb
    ports:
      - 8080:8080
      - 30005:30005
      - 30003:30003
    environment:
      - TZ=America/New_York
      - READSB_DCFILTER=true
      - READSB_DEVICE_TYPE=rtlsdr
      - READSB_RTLSDR_DEVICE=00001090
      - READSB_FIX=true
      - READSB_GAIN=autogain
      - READSB_LAT=-33.33333
      - READSB_LON=111.11111
      - READSB_MODEAC=true
      - READSB_RX_LOCATION_ACCURACY=2
      - READSB_STATS_RANGE=true
      - READSB_NET_ENABLE=true
      - READSB_NET_CONNECTOR=dump978,37981,raw_in
    volumes:
      - readsbpb_rrd:/run/collectd
      - readsbpb_autogain:/run/autogain

  dump978:
    image: mikenye/dump978
    tty: true
    container_name: dump978
    restart: always
    devices:
      - /dev/bus/usb:/dev/bus/usb/
    ports:
      - 30978:30978
      - 30979:30979
      - 37981:37981
    environment:
      - TZ=America/New_York
      - DUMP978_RTLSDR_DEVICE=00000978

  adsbx:
    image: mikenye/adsbexchange
    tty: true
    container_name: adsbx
    restart: always
    depends_on:
      - readsb
      - dump978
    environment:
      - BEASTHOST=readsb
      - LAT=-33.33333
      - LONG=111.11111
      - ALT=100ft
      - SITENAME=YOURSITENAME
      - UUID=YOURADSBXUUID
      - TZ=America/New_York

  piaware:
    image: mikenye/piaware:latest
    tty: true
    container_name: piaware
    restart: always
    depends_on:
      - readsb
      - dump978
    ports:
      - 8081:80
    environment:
      - TZ=America/New_York
      - LAT=33.33333
      - LONG=-111.11111
      - ALT=100ft
      - FEEDER_ID=YOURFEEDERID
      - BEASTHOST=readsb
      - UAT_RECEIVER_TYPE=relay
      - UAT_RECEIVER_HOST=dump978
```

You should now be feeding ADSB-ES & UAT to ADSBExchange and FlightAware.

## Environment Variables

### Container Options

| Variable | Description | Default |
|----------|-------------|---------|
| `TZ` | Local timezone in ["TZ database name" format](<https://en.wikipedia.org/wiki/List_of_tz_database_time_zones>). | `UTC` |

### `dump978-fa` General Options

Where the default value is "Unset", `dump978-fa`'s default will be used.

| Variable | Description | Controls which `dump978-fa` option | Default |
|----------|-------------|--------------------------------|---------|
| `DUMP978_DEVICE_TYPE` | Currently only `rtlsdr` is supported. If you have another type of radio, please open an issue and I'll try to get it added. | `--sdr driver=` | `rtlsdr` |
| `DUMP978_SDR_AGC` | Set to any value to enable SDR AGC. | `--sdr-auto-gain` | Unset |
| `DUMP978_SDR_GAIN` | Set SDR gain in dB. | `--sdr-gain` | Unset |
| `DUMP978_SDR_PPM` | Set SDR frequency correction in PPM. | `--sdr-ppm` | Unset |
| `DUMP978_JSON_STDOUT` | Write decoded json to the container log. Useful for troubleshooting, but don't leave enabled! | `--json-stdout` | Unset |

### `dump978-fa` RTL-SDR Options

Use with `DUMP978_DEVICE_TYPE=rtlsdr`.

Where the default value is "Unset", `dump978-fa`'s default will be used.

| Variable | Description | Controls which `dump978-fa` option | Default |
|----------|-------------|--------------------------------|---------|
| `DUMP978_RTLSDR_DEVICE` | If using Select device by serial number. | `--sdr driver=rtlsdr,serial=` | Unset |

### InfluxDB Options

These variables control the sending of flight data and dump978 metrics to [InfluxDB](https://docs.influxdata.com/influxdb/) (via a built-in instance of [Telegraf](https://docs.influxdata.com/telegraf/)).

| Variable | Description | Default |
|----------|-------------|---------|
| `INFLUXDBURL` | The full HTTP URL for your InfluxDB instance. | Unset |
| `INFLUXDBUSERNAME` | If using authentication, a username for your InfluxDB instance. If not using authentication, leave unset. | Unset |
| `INFLUXDBPASSWORD` | If using authentication, a password for your InfluxDB instance. If not using authentication, leave unset. | Unset |

### Prometheus Options

These variables control exposing flight data to [Prometheus](https://prometheus.io) (via a built-in instance of [Telegraf](https://docs.influxdata.com/telegraf/)).

| Variable | Description | Default |
|----------|-------------|---------|
| `ENABLE_PROMETHEUS` | Set to any string to enable Prometheus support | Unset |
| `PROMETHEUSPORT` | The port that the prometheus client will listen on | `9273` |
| `PROMETHEUSPATH` | The path that the prometheus client will publish metrics on | `/metrics` |

## Logging

* All processes are logged to the container's stdout, and can be viewed with `docker logs [-f] container`.

## Getting help

Please feel free to [open an issue on the project's GitHub](https://github.com/mikenye/docker-dump978/issues).

I also have a [Discord channel](https://discord.gg/sTf9uYF), feel free to [join](https://discord.gg/sTf9uYF) and converse.

## Changelog

See the project's [commit history](https://github.com/mikenye/docker-dump978/commits/master).
