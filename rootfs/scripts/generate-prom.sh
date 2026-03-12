#!/command/with-contenv bash
# shellcheck shell=bash

# generate prom file for consumption by for example docker-telegraf-adsb
# currently this only has autogain as the other metrics can be generated in docker-telegraf-adsb

OUT=/run/skyaware978/stats.prom
TMP=/run/skyaware978/stats.prom.tmp

function generate() {
    if [[ -f "$GAIN_VALUE_FILE" ]]; then
        echo "autogain_current_value $(cat "$GAIN_VALUE_FILE")"
    fi
}

while sleep 60; do
    generate > "$TMP"
    mv -f "$TMP" "$OUT"
done


