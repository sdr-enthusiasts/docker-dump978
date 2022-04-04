# sdr-enthusiasts/docker-dump978

[![Docker Image Size (tag)](https://img.shields.io/docker/image-size/mikenye/dump978/latest)](https://hub.docker.com/r/mikenye/dump978)
[![Discord](https://img.shields.io/discord/734090820684349521)](https://discord.gg/sTf9uYF)

This container provides the FlightAware 978MHz UAT decoder, and the ADSBExchange fork of `uat2esnt`, working together in harmony. A rare example of harmony in these turblent times. :-)

This container can be used alongside [sdr-enthusiasts/docker-readsb-protobuf](https://github.com/sdr-enthusiasts/docker-readsb-protobuf) to provide UAT into several feeders.

This container also contains InfluxData's [Telegraf](https://docs.influxdata.com/telegraf/), and can send flight data and `dump978` metrics to InfluxDB (if wanted - not started by default).

UAT is currently only used in the USA, so don't bother with this if you're not located in the USA.

## Ports

The container listens on the following TCP ports:

| Port | Description |
|------|-------------|
| `30978` | Raw UAT output (NOT compatible with `readsb`'s `raw_in`!) |
| `30979` | Decoded JSON output |
| `37981` | `uat2esnt` converted output. This IS compatible with `readsb`'s `raw_in`. |

## Paths & Volumes

| Path (inside container) | Details |
|-------------------------|---------|
| `/run/autogain` | Map this to persistant storage if you set `DUMP978_SDR_GAIN=autogain` |

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
    ghcr.io/sdr-enthusiasts/docker-dump978:latest
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
    image: ghcr.io/sdr-enthusiasts/docker-readsb-protobuf:latest
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
    image: ghcr.io/sdr-enthusiasts/docker-dump978:latest
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
| `LAT` | Latitude of your receiver. Only required if you want range statistics for InfluxDB or Prometheus, or if you are using the autogain script. | Unset |
| `LON` | Longitude of your receiver. Only required if you want range statistics for InfluxDB or Prometheus, or if you are using the autogain script. | Unset |

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

| Variable | Description | Controls which `dump978-fa` option | Default |
|----------|-------------|--------------------------------|---------|
| `DUMP978_RTLSDR_DEVICE` | If using Select device by serial number. | `--sdr driver=rtlsdr,serial=` | Unset |

### Auto-Gain Options

These variables control the auto-gain system (explained further below). These should rarely need changing from the defaults.

| Variable | Description | Default |
|----------|-------------|---------|
| `AUTOGAIN_INITIAL_PERIOD` | How long each gain level should be measured during auto-gain initialisation (ie: "roughing in"), in seconds. | `7200` (2 hours) |
| `AUTOGAIN_INITIAL_MSGS_ACCEPTED` | How many locally accepted messages should be received per gain level during auto-gain initialisaion to ensure accurate measurement. | `100000` |
| `AUTOGAIN_FINETUNE_PERIOD` | How long each gain level should be measured during auto-gain fine-tuning, in seconds. | `604800` (7 days) |
| `AUTOGAIN_FINETUNE_MSGS_ACCEPTED` | How many locally accepted messages should be received per gain level during auto-gain fine-tuning to ensure accurate measurement. | `700000` |
| `AUTOGAIN_FINISHED_PERIOD` | How long between the completion of fine-tuning (and ultimately setting a preferred gain), and re-running the entire process. | `31536000` (1 year) |
| `AUTOGAIN_MAX_GAIN_VALUE` | The maximum gain setting in dB that will be used by auto-gain. | `49.6` (max supported by `readsb`) |
| `AUTOGAIN_MIN_GAIN_VALUE` | The minimum gain setting in dB that will be used by auto-gain. | `0.0` (min supported by `readsb`) |
| `AUTOGAIN_PERCENT_STRONG_MESSAGES_MAX` | The maximum percentage of "strong messages" auto-gain will aim for. | `10.0` |
| `AUTOGAIN_PERCENT_STRONG_MESSAGES_MIN` | The minimum percentage of "strong messages" auto-gain will aim for. | `0.5` |
| `AUTOGAIN_SERVICE_PERIOD` | How often the auto-gain system will check results and perform actions, in seconds | `900` (15 minutes) |

### InfluxDB Options

These variables control the sending of flight data and dump978 metrics to [InfluxDB](https://docs.influxdata.com/influxdb/) (via a built-in instance of [Telegraf](https://docs.influxdata.com/telegraf/)).

| Variable | Description | Default |
|----------|-------------|---------|
| `INFLUXDBURL` | The full HTTP URL for your InfluxDB instance. Required for both InfluxDB v1 and v2. | Unset |
| `INFLUXDBUSERNAME` | If using authentication, a username for your InfluxDB instance. If not using authentication, leave unset. Not required for InfluxDB v2. | Unset |
| `INFLUXDBPASSWORD` | If using authentication, a password for your InfluxDB instance. If not using authentication, leave unset. Not required for InfluxDB v2. | Unset |
| `INFLUXDB_V2` | Set to a non empty value to enable InfluxDB V2 output. | Unset |
| `INFLUXDB_V2_BUCKET` | Required if `INFLUXDB_V2` is set, bucket must already exist in your InfluxDB v2 instance. | Unset |
| `INFLUXDB_V2_ORG` | Required if `INFLUXDB_V2` is set. | Unset |
| `INFLUXDB_V2_TOKEN` | Required if `INFLUXDB_V2` is set. | Unset |
| `INFLUXDB_SKIP_AIRCRAFT` | Set to any value to skip publishing aircraft data to InfluxDB to minimize bandwidth and database size. | Unset |

### Prometheus Options

These variables control exposing flight data to [Prometheus](https://prometheus.io) (via a built-in instance of [Telegraf](https://docs.influxdata.com/telegraf/)).

| Variable | Description | Default |
|----------|-------------|---------|
| `ENABLE_PROMETHEUS` | Set to any string to enable Prometheus support | Unset |
| `PROMETHEUSPORT` | The port that the prometheus client will listen on | `9273` |
| `PROMETHEUSPATH` | The path that the prometheus client will publish metrics on | `/metrics` |

## Auto-Gain system

An automatic gain adjustment system is included in this container, and can be activated by setting the environment variable `DUMP978_SDR_GAIN` to `autogain`. You should also map `/run/autogain` to persistant storage, otherwise the auto-gain system will start over each time the container is restarted. You should also ensure `LAT` and `LON` are set because the script uses the maximum range as a metric for choosing the best gain level.

*Why is this written in bash?* Because I wanted to keep the container size down and not have to install an interpreter like python. I don't know C/Go/Perl or any other languages.

Auto-gain will take several weeks to initially (over the period of a week or so) work out feasible maximum and minimum gain levels for your environment. It will then perform a fine-tune process to find the optimal gain level.

During each process, gain levels are ranked as follows:

* The range achievable by each gain level
* The signal-to-noise ratio of the receiver

The ranking process is done by sorting the gain levels for each statistic from worst to best, then awarding points. 0 points are awarded for the worst gain level, 1 point for the next gain level all the way up to several points for the best gain level (total number of points is the number of gain levels tested). The number of points for each gain level is totalled, and the optimal gain level is the level with the largest number of points. Any gain level with a percentage of "strong signals" outside of `AUTOGAIN_PERCENT_STRONG_MESSAGES_MAX` and `AUTOGAIN_PERCENT_STRONG_MESSAGES_MIN` is discarded.

Using this method, auto-gain tried to achieve the best balance of range, tracks and signal-to-noise ratio, whilst ensuring an appropriate number of "strong signals".

The auto-gain system will work as follows:

### Initialisation Stage

In the initialisation process:

1. `dump978` is set to maximum gain (`AUTOGAIN_MAX_GAIN_VALUE`).
1. Results are collected up to `AUTOGAIN_INITIAL_PERIOD` (up to 2 hours by default).
1. Check to ensure at least `AUTOGAIN_INITIAL_MSGS_ACCEPTED` messages have been locally accepted (1,000,000 by default). If not, continue collecting data for up to 24 hours. This combination of time and number of messages ensures we have enough data to make a valid initial assessment of each gain level.
1. Gain level is lowered by one level.
1. Gain levels are reviewed from lowest to highest gain level. If there have been gain levels resulting in a percentage of strong messages between `AUTOGAIN_PERCENT_STRONG_MESSAGES_MAX` and `AUTOGAIN_PERCENT_STRONG_MESSAGES_MIN`, and there have been three consecutive gain levels above `AUTOGAIN_PERCENT_STRONG_MESSAGES_MAX`, auto-gain lowers the maximum gain level.
1. Gain levels are reviewed from highest to lowest gain level. If there have been gain levels resulting in a percentage of strong messages between `AUTOGAIN_PERCENT_STRONG_MESSAGES_MAX` and `AUTOGAIN_PERCENT_STRONG_MESSAGES_MIN`, and there have been three consecutive gain levels below `AUTOGAIN_PERCENT_STRONG_MESSAGES_MIN`, auto-gain discontinues testing gain levels.

Auto-gain then moves onto the fine-tuning stage.

### Fine-Tuning Stage

In the fine-tuning process:

1. `dump978` is set to maximum gain level chosen at the end of the initialisation process.
1. Results are collected up to `AUTOGAIN_FINETUNE_PERIOD` (7 days by default).
1. Check to ensure at least `AUTOGAIN_FINETUNE_MSGS_ACCEPTED` messages have been locally accepted (7,000,000 by default). If not, continue collecting data for up to 48 hours. This combination of time and number of messages ensures we have enough data to make an accurate assessment of each gain level, and by using 7 days this ensures any peaks/troughs in data due to quiet/busy days of the week do not skew results.
1. Gain level is lowered by one level until the minimum gain level chosen at the end of the initialisation process is reached.

At this point, all of the tested gain levels are ranked based on the criterea discussed above.

The gain level with the most points is chosen, and `dump978` is set to this gain level.

Auto-gain then moves onto the finished stage.

### Finished Stage

In the finished stage, auto-gain does nothing (as `dump978` is operating at optimal gain) for `AUTOGAIN_FINISHED_PERIOD` (1 year by default). After this time, auto-gain reverts to the initialisation stage and the entire process is completed again. This makes sure your configuration is always running at the optimal gain level as your RTLSDR ages.

### State/Log/Stats Files

All files for auto-gain are located at `/run/autogain` within the container. They should not be modified by hand.

### Forcing auto-gain to re-run from scratch

Run `docker exec <container_name> rm /run/autogain/*` to remove all existing auto-gain state data. Restart the container and auto-gain will detect this and re-start at initialisation stage.

## Logging

* All processes are logged to the container's stdout, and can be viewed with `docker logs [-f] container`.

## Getting help

Please feel free to [open an issue on the project's GitHub](https://github.com/sdr-enthusiasts/docker-dump978/issues).

I also have a [Discord channel](https://discord.gg/sTf9uYF), feel free to [join](https://discord.gg/sTf9uYF) and converse.
