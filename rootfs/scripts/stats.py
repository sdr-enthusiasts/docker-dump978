#!/usr/bin/with-contenv python3

import collections
from copy import deepcopy
import json
import math
from os import environ
import socket
import threading
import time

###############################################################################
# Helper functions for logging
###############################################################################

stdout_lock = threading.Lock()


def LOGW(msg):
    with stdout_lock:
        print("WARNING: " + str(msg))


def LOGD(msg):
    if DEBUG:
        with stdout_lock:
            print("DEBUG: " + str(msg))

###############################################################################
# Helper functions to various stat types
###############################################################################


# Extract a (potentially nested) key or list of keys from a dict
def extract(msg, keys):
    try:
        out = []
        for key in keys:
            val = msg
            for k in key:
                val = val[k]
            out.append(val)
        return out
    except BaseException as e:
        LOGW("%s : %s looking for keys %s" % (type(e), str(e), str(keys)))
        LOGW("Offending message JSON : %s" % msg)
        raise e


def parse_cnt(keys=None, test=None):
    def wrapper(store, msg):
        val = extract(msg, keys)[0]
        if val is not None:
            if test is None or test(val):
                store[0] += 1
    return wrapper


def get_cnt(store):
    return store[0]


def aggregate_cnt(old, new):
    old[0] = old[0] + new[0]


def parse_range(origin):
    def wrapper(store, msg):
        dist, brng = gps_dist(origin, (msg["position"]["lat"], msg["position"]["lon"]))
        store[brng] = max(store[brng], dist)
    return wrapper


def aggregate_range(old, new):
    for i, v in enumerate(old):
        old[i] = max(v, new[i])


def parse_max(keys):
    def wrapper(store, msg):
        try:
            val = extract(msg, keys)[0]
            if store[0] is None:
                store[0] = float(val)
            else:
                store[0] = max(store[0], float(val))
        except BaseException:
            pass
    return wrapper


def get_max(store):
    return max(store)


def aggregate_max(old, new):
    if new[0] is None:
        return
    if old[0] is None:
        old[0] = new[0]
        return
    old[0] = max(old[0], new[0])


def parse_avg(keys):
    def wrapper(store, msg):
        val = extract(msg, keys)[0]
        if val is not None:
            store[0] += float(val)
            store[1] += 1
    return wrapper


def get_avg(store):
    try:
        return store[0] / store[1]
    except BaseException:
        return None


def aggregate_avg(old, new):
    old = [x + y for x, y in zip(old, new)]


def parse_set(keys, mask=None):
    def wrapper(store, msg):
        val = extract(msg, keys)[0]
        if val is not None:
            if mask is None or mask in val:
                store.add(msg["address"])
    return wrapper


def aggregate_set(old, new):
    old |= new

###############################################################################
# Classes that define individual stats and a collection of stats over a period
###############################################################################


# Defines a single statistic to extract from decoded JSON messages
class Stat:
    def __init__(self, name, initializer, parser, getter, aggregator, test=None):
        self.name = name
        self._initialize = initializer
        self._parse = parser
        self._get = getter
        self._aggregate = aggregator
        self._test = test
        self._store = initializer()

    def initialize(self):
        self._store = self._initialize()

    def parse(self, msg):
        self._parse(self._store, msg)

    def get(self):
        return self._get(self._store)

    def aggregate(self, new):
        self._aggregate(self._store, new._store)


# Defines a collection of statistics to store over a 1 minute period
class Stats_1min:
    def __init__(self):
        self.stats = list()

    def add(self, stat):
        self.stats.append(stat)

    def initialize(self):
        for stat in self.stats:
            stat.initialize()

    def parse(self, msg):
        for stat in self.stats:
            stat.parse(msg)

    def aggregate(self, new):
        for n in new.stats:
            found = False
            for stat in self.stats:
                if n.name == stat.name:
                    stat.aggregate(n)
                    found = True
                    break
            if not found:
                self.stats.append(n)

    def get(self, name):
        for stat in self.stats:
            if stat.name is name:
                return stat
        return None

    def to_dict(self):
        out = dict()
        for stat in self.stats:
            val = stat.get()
            if val is not None:
                out[stat.name] = stat.get()
        return out

    def __str__(self):
        return json.dumps(self.to_dict())

###############################################################################
# Global variables
###############################################################################


# Set to True to enable debug messages  pass
DEBUG = True

# Deque of historical statistics
history = collections.deque([], 15)

###############################################################################
# Functions
###############################################################################


# meters and angle between two GPS coordinates
def gps_dist(home, destination):
    lat1, lon1 = home
    lat2, lon2 = destination
    radius = 6371000  # m

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    coslat1 = math.cos(math.radians(lat1))
    coslat2 = math.cos(math.radians(lat2))
    sinlat1 = math.sin(math.radians(lat1))
    sinlat2 = math.sin(math.radians(lat2))

    a = math.sin(dlat / 2)**2 + coslat1 * coslat2 * math.sin(dlon / 2)**2
    dist = 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    x = coslat2 * math.sin(dlon)
    y = coslat1 * sinlat2 - sinlat1 * coslat2 * math.cos(dlon)
    brng = math.degrees(math.atan2(x, y))

    return round(dist), round(brng / 5) % 72


# Aggregate stats over last 1, 5, and 15 minutes
# Write the output files
def aggregate(raw_lock, raw_latest, json_lock, json_latest, polar_range):
    with json_lock:
        history.appendleft(deepcopy(json_latest))
        json_latest.initialize()

    with raw_lock:
        history[0].aggregate(deepcopy(raw_latest))
        raw_latest.initialize()

    last_15min = deepcopy(history[0])

    for i, d in enumerate(history):
        if i == 0:
            continue
        last_15min.aggregate(d)
        if i == 3:
            last_5min = deepcopy(last_15min)
    out = dict()

    out["last_1min"] = history[0].to_dict()
    if len(history) >= 5:
        out["last_5min"] = last_5min.to_dict()
    if len(history) >= 15:
        out["last_15min"] = last_15min.to_dict()

    with open("/run/stats/stats.json", "w") as f:
        json.dump(out, f, indent=4, sort_keys=True)
        f.write("\n")

    if polar_range is not None:
        polar_range.aggregate(history[0].get("max_distance_m"))
        with open("/run/stats/polar_range.influx", "w") as fout:
            for b, d in enumerate(polar_range._store):
                fout.write("polar_range,bearing=%02d range=%d %d\n" % (b, d, time.time_ns()))


# Parse decoded JSON messages
def parse_json(fjson, json_lock, json_latest):
    LOGD("listening for json data")

    for msg in fjson:
        with json_lock:
            json_latest.parse(json.loads(msg))


# Parse raw UAT messages
# Currently just counts the number of messages
def parse_raw(fraw, raw_lock, raw_latest):
    LOGD("listening for raw data")

    for msg in fraw:
        with raw_lock:
            try:
                rssi_begin = msg.index("rssi=") + 5
                rssi_end = rssi_begin + msg[rssi_begin:].index(";")
                raw_latest.parse({"rssi": float(msg[rssi_begin:rssi_end])})
            except ValueError:
                LOGW("Did not find RSSI in raw message %s" % msg)


def main():
    host = '127.0.0.1'
    raw_port = 30978
    json_port = 30979

    raw_sock = socket.socket()
    raw_sock.connect((host, raw_port))
    fraw = raw_sock.makefile(buffering=1)

    LOGD("connected to dump978 raw output")

    json_sock = socket.socket()
    json_sock.connect((host, json_port))
    fjson = json_sock.makefile(buffering=1)

    LOGD("connected to dump978 JSON output")

    raw_lock = threading.Lock()
    raw_latest = Stats_1min()
    raw_latest.add(Stat("total_raw_messages", lambda: [0], parse_cnt([["rssi"]]), get_cnt, aggregate_cnt))
    raw_latest.add(Stat("strong_raw_messages", lambda: [0], parse_cnt([["rssi"]], lambda v: float(v) > -3.0), get_cnt, aggregate_cnt))
    raw_latest.add(Stat("avg_raw_rssi", lambda: [0, 0], parse_avg([["rssi"]]), get_avg, aggregate_avg))
    raw_latest.add(Stat("peak_raw_rssi", lambda: [None], parse_max([["rssi"]]), get_max, aggregate_max))

    json_lock = threading.Lock()
    json_latest = Stats_1min()
    json_latest.add(Stat("total_accepted_messages", lambda: [0], parse_cnt([["address"]]), get_cnt, aggregate_cnt))
    json_latest.add(Stat("strong_accepted_messages", lambda: [0], parse_cnt([["metadata", "rssi"]], lambda v: float(v) > -3.0), get_cnt, aggregate_cnt))
    json_latest.add(Stat("avg_accepted_rssi", lambda: [0, 0], parse_avg([["metadata", "rssi"]]), get_avg, aggregate_avg))
    json_latest.add(Stat("peak_accepted_rssi", lambda: [None], parse_max([["metadata", "rssi"]]), get_max, aggregate_max))
    json_latest.add(Stat("total_tracks", set, parse_set([["address"]]), len, aggregate_set))
    json_latest.add(Stat("airborne_tracks", set, parse_set([["airground_state"]], "airborne"), len, aggregate_set))
    json_latest.add(Stat("ground_tracks", set, parse_set([["airground_state"]], "ground"), len, aggregate_set))
    json_latest.add(Stat("supersonic_tracks", set, parse_set([["airground_state"]], "supersonic"), len, aggregate_set))
    json_latest.add(Stat("adsb_tracks", set, parse_set([["address_qualifier"]], "adsb"), len, aggregate_set))
    json_latest.add(Stat("tisb_tracks", set, parse_set([["address_qualifier"]], "tisb"), len, aggregate_set))
    json_latest.add(Stat("vehicle_tracks", set, parse_set([["address_qualifier"]], "vehicle"), len, aggregate_set))
    json_latest.add(Stat("beacon_tracks", set, parse_set([["address_qualifier"]], "beacon"), len, aggregate_set))
    json_latest.add(Stat("adsr_tracks", set, parse_set([["address_qualifier"]], "adsr"), len, aggregate_set))

    try:
        origin = (float(environ["LAT"]), float(environ["LON"]))

        max_dist = Stat("max_distance_m", lambda: [0] * 72, parse_range(origin), get_max, aggregate_range)
        json_latest.add(max_dist)
        polar_range = deepcopy(max_dist)
    except KeyError:
        polar_range = None
        LOGW("receiver location not set")

    threading.Thread(target=parse_raw, args=(fraw, raw_lock, raw_latest)).start()
    threading.Thread(target=parse_json, args=(fjson, json_lock, json_latest)).start()

    while True:
        aggregate(raw_lock, raw_latest, json_lock, json_latest, polar_range)
        time.sleep(60)


if __name__ == "__main__":
    main()
