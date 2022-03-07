#!/usr/bin/with-contenv python3

# pylint: disable=C0103
# pylint: disable=C0114
# pylint: disable=C0115
# pylint: disable=C0116
# pylint: disable=W0603

import copy
import json
import math
import collections
import socket
import threading
import time

################################################################################
# Helper functions for logging
################################################################################

def LOGW(msg):
    print("WARNING: " + str(msg))

def LOGD(msg):
    if DEBUG:
        print("DEBUG: " + str(msg))

################################################################################
# Helper functions to initialize and parse various stats
################################################################################

def aggregate_set(old, new):
    old.store |= new.store

def parse_total_tracks(store, msg):
    store.add(msg["address"])

################################################################################
# Classes that define individual stats and a collection of stats over a period
################################################################################

# Defines a single statistic to extract from decoded JSON messages
class Stat:
    name = None
    _initialize = None
    _parse = None
    _get = None
    store = None

    def __init__(self, name, initializer, parser, getter, aggregator):
        self.name = name
        self._initialize = initializer
        self._parse = parser
        self._get = getter
        self._aggregate = aggregator
        self.store = initializer()

    def initialize(self):
        self.store = self._initialize()

    def parse(self, msg):
        self._parse(self.store, msg)

    def get(self):
        return self._get(self.store)

    def aggregate(self, new):
        return self._aggregate(self, new)

# Defines a collection of statistics to store over a 1 minute period
class Stats_1min:
    stats = list()

    def __init__(self):
## Statistics, grouped by type
#stats_def = [{"total_tracks": },
#             {"tracks_with_position": },
#             {"airborne_tracks": },
#             {"ground_tracks": },
#             {"supersonic_tracks": },
#             {"adsb_tracks": },
#             {"tisb_tracks": },
#             {"beacon_tracks": },
#             {"adsr_tracks": }]
        self.stats.append(Stat("total_tracks", set, parse_total_tracks, len, aggregate_set))

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

    def to_dict(self):
        out = dict()
        for stat in self.stats:
            out[stat.name] = stat.get()
        return out

################################################################################
# Global variables
################################################################################

# Set to True to enable debug messages  pass
DEBUG = True

# Deque of historical statistics
history = collections.deque([], 15)

# JSON socket live stats and mutex
latest = Stats_1min()
json_mutex = threading.Lock()

# Number of raw messages received and mutex
raw_cnt = 0
raw_mutex = threading.Lock()

################################################################################
# Functions
################################################################################

# meters and angle between two GPS coordinates
def gps_dist(origin, destination):
    lat1, lon1 = origin
    lat2, lon2 = destination
    radius = 6371000 # m

    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    coslat1 = math.cos(math.radians(lat1))
    coslat2 = math.cos(math.radians(lat2))
    sinlat1 = math.sin(math.radians(lat1))
    sinlat2 = math.sin(math.radians(lat2))

    a = math.sin(dlat/2)**2 + coslat1 * coslat2 * math.sin(dlon/2)**2
    dist = 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1-a))

    x = coslat2 * math.sin(dlon)
    y = coslat1 * sinlat2 - sinlat1 * coslat2 * math.cos(dlon)
    brng = math.degrees(math.atan2(x,y))

    return round(dist), round(brng/5) % 72

#def parse(msg, origin):
#  latest["total_tracks"].add(msg["address"])
#  latest["rssi"].append(float(msg["metadata"]["rssi"]))

#  try:
#    if msg["airground_state"] == "ground":
#      latest["ground_tracks"].add(msg["address"])
#    elif msg["airground_state"] == "airborne":
#      latest["airborne_tracks"].add(msg["address"])
#    elif msg["airground_state"] == "supersonic":
#      latest["supersonic_tracks"].add(msg["address"])
#  except KeyError:
#    pass

#  try:
#    if "adsb" in msg["address_qualifier"]:
#      latest["adsb_tracks"].add(msg["address"])
#    elif "tisb" in msg["address_qualifier"]:
#      latest["tisb_tracks"].add(msg["address"])
#    elif "vehicle" == msg["address_qualifier"]:
#      latest["vehicle_tracks"].add(msg["address"])
#    elif "fixed_beacon" == msg["address_qualifier"]:
#      latest["beacon_tracks"].add(msg["address"])
#    elif "adsr_other" == msg["address_qualifier"]:
#      latest["adsr_tracks"].add(msg["address"])
#  except KeyError:
#    pass

#  try:
#    pos = (float(msg["position"]["lat"]), float(msg["position"]["lon"]))
#    latest["tracks_with_position"].add(msg["address"])
#    if origin is not None:
#      dist, brng = gps_dist(origin, pos)
#      latest["dist"][brng] = max(dist, latest["dist"][brng])
#      latest["max_dist"][brng] = max(dist, latest["max_dist"][brng])
#  except KeyError:
#    pass

#def extract(lastx):
#  stats = dict()

#  stats["strong_messages"]      = sum([1 if r > -3.0 else 0 for r in lastx["rssi"]])
#  stats["total_messages"]       = len(lastx["rssi"])
#  for s in set_stats:
#    stats[s] = len(lastx[s])

#  if len(lastx["rssi"]) > 0:
#    stats["peak_rssi"] = max(lastx["rssi"])
#    stats["avg_rssi"] = sum(lastx["rssi"])/len(lastx["rssi"])

#    if lastx["max_dist"] is not None:
#      stats["max_distance_m"] = max(lastx["dist"])
#      stats["max_distance_nmi"] = max(lastx["dist"]) // 1852

#  return stats

# Aggregate stats over last 1, 5, and 15 minutes
# Write the output files
def aggregate():
    global latest
    global json_mutex
    global raw_cnt
    global raw_mutex

    with json_mutex:
        history.appendleft(copy.deepcopy(latest))
        latest.initialize()

    last_15min = copy.deepcopy(history[0])

    for i,d in enumerate(history):
        if i == 0:
            continue
        last_15min.aggregate(d)
        if i == 3:
            last_5min = copy.deepcopy(last_15min)
    out = dict()

    out["last_1min"] = history[0].to_dict()
    if len(history) >= 5:
        out["last_5min"] = last_5min.to_dict()
    if len(history) >= 15:
        out["last_15min"] = last_15min.to_dict()

    with raw_mutex:
        out["total_messages"] = raw_cnt
        raw_cnt = 0

    with open("/run/stats/stats.json", "w") as f:
        json.dump(out, f, indent=4, sort_keys=True)
        f.write("\n")

#  if stats_hist[0]["max_dist"] is not None:
#    with open("/run/stats/polar_range.influx", "w") as fout:
#      for b, d in enumerate(stats_hist[0]["max_dist"]):
#        fout.write("polar_range,bearing=%02d range=%d %d\n" % (b, d, time.time_ns()))

# Parse decoded JSON messages
def parse_json(fjson):
    global latest
    global json_mutex

    LOGD("listening for json data")

    for msg_str in fjson:
        msg = json.loads(msg_str)
        with json_mutex:
            try:
                latest.parse(msg)
            except KeyError as e:
                LOGW("KeyError : %s" % str(e))
                LOGW("Offending message JSON : %s" % msg_str)

# Parse raw UAT messages
# Currently just counts the number of messages
def parse_raw(fraw):
    global raw_cnt
    global raw_mutex

    LOGD("listening for raw data")

    for msg in fraw:
        with raw_mutex:
            raw_cnt += 1

def main():
#  try:
#    origin = (float(os.environ["LAT"]), float(os.environ["LON"]))
#    latest["max_dist"] = [0] * 72
#  except:
#    LOGW("receiver location not set")
#    origin = None
#    latest["max_dist"] = None

    host = '127.0.0.1'
    raw_port = 30978
    json_port = 30979

    raw_sock = socket.socket()
    raw_sock.connect((host, raw_port))
    fraw = raw_sock.makefile(buffering=1)

    json_sock = socket.socket()
    json_sock.connect((host, json_port))
    fjson = json_sock.makefile(buffering=1)

    LOGD("connected to dump978 JSON output")

    threading.Thread(target=parse_raw, args=(fraw,)).start()
    threading.Thread(target=parse_json, args=(fjson,)).start()

    while True:
        time.sleep(60)
        aggregate()

if __name__ == "__main__":
    main()
