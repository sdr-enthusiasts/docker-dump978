#!/command/with-contenv bash
# shellcheck shell=bash

# generate prom file for consumption by for example docker-telegraf-adsb
# currently this only has autogain as the other metrics can be generated in docker-telegraf-adsb

OUT=/run/skyaware978/stats.prom
TMP=/run/skyaware978/stats.prom.tmp

function generate() {
    if [[ -f "$AUTOGAIN_CURRENT_VALUE_FILE" ]]; then
        echo "autogain_current_value=$(cat "$AUTOGAIN_CURRENT_VALUE_FILE")"
        echo "autogain_max_value=$(cat "$AUTOGAIN_MAX_GAIN_VALUE_FILE")"
        echo "autogain_min_value=$(cat "$AUTOGAIN_MIN_GAIN_VALUE_FILE")"
        echo "autogain_pct_strong_messages_max=$AUTOGAIN_PERCENT_STRONG_MESSAGES_MAX"
        echo "autogain_pct_strong_messages_min=$AUTOGAIN_PERCENT_STRONG_MESSAGES_MIN"
    fi
}

while sleep 60; do
    generate > "$TMP"
    mv -f "$TMP" "$OUT"
done


