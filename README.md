# mikenye/dump978

## Environment Variables

### `dump978-fa` General Options

Where the default value is "Unset", `dump978-fa`'s default will be used.

| Variable | Description | Controls which `dump978-fa` option | Default |
|----------|-------------|--------------------------------|---------|
| `DUMP978_RAW_PORT` | Listen for connections and provide raw messages on this port. | `--raw-port` | `30978` |
| `DUMP978_JSON_PORT` | Listen for connections and provide decoded JSON on this port. | `--json-port` | `30979` |
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
