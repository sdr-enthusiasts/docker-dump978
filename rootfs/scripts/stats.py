#!/usr/bin/with-contenv python3

# Collect last 1 min stats from dump978 JSON feed

import copy
import json
import math
import os
import collections
import socket
import threading
import time

################################################################################
# Global variables
################################################################################

# Statistics, grouped by type
set_stats = ["total_tracks", "tracks_with_position", "airborne_tracks",
             "ground_tracks", "supersonic_tracks", "adsb_tracks", "tisb_tracks",
             "beacon_tracks", "adsr_tracks"]

# Deque of historical statistics
stats_hist = collections.deque([], 15)

# Live stats dictionary and its mutex
latest = {}
mutex = threading.Lock()

################################################################################
# Functions
################################################################################

def LOG(msg):
  pass
  print(msg)

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

def init():
  global latest
  latest["rssi"]                 = list()
  latest["dist"]                 = [0] * 72
  for s in set_stats:
    latest[s] = set()

def parse(msg, origin):
  latest["total_tracks"].add(msg["address"])
  latest["rssi"].append(float(msg["metadata"]["rssi"]))

  try:
    if msg["airground_state"] == "ground":
      latest["ground_tracks"].add(msg["address"])
    elif msg["airground_state"] == "airborne":
      latest["airborne_tracks"].add(msg["address"])
    elif msg["airground_state"] == "supersonic":
      latest["supersonic_tracks"].add(msg["address"])
  except KeyError:
    pass

  try:
    if "adsb" in msg["address_qualifier"]:
      latest["adsb_tracks"].add(msg["address"])
    elif "tisb" in msg["address_qualifier"]:
      latest["tisb_tracks"].add(msg["address"])
    elif "vehicle" == msg["address_qualifier"]:
      latest["vehicle_tracks"].add(msg["address"])
    elif "fixed_beacon" == msg["address_qualifier"]:
      latest["beacon_tracks"].add(msg["address"])
    elif "adsr_other" == msg["address_qualifier"]:
      latest["adsr_tracks"].add(msg["address"])
  except KeyError:
    pass

  try:
    pos = (float(msg["position"]["lat"]), float(msg["position"]["lon"]))
    latest["tracks_with_position"].add(msg["address"])
    if origin is not None:
      dist, brng = gps_dist(origin, pos)
      latest["dist"][brng] = max(dist, latest["dist"][brng])
      latest["max_dist"][brng] = max(dist, latest["max_dist"][brng])
  except KeyError:
    pass

def extract(lastx):
  stats = dict()

  stats["strong_messages"]      = sum([1 if r > -3.0 else 0 for r in lastx["rssi"]])
  stats["total_messages"]       = len(lastx["rssi"])
  for s in set_stats:
    stats[s] = len(lastx[s])

  if len(lastx["rssi"]) > 0:
    stats["peak_rssi"] = max(lastx["rssi"])
    stats["avg_rssi"] = sum(lastx["rssi"])/len(lastx["rssi"])

    if lastx["max_dist"] is not None:
      stats["max_distance_m"] = max(lastx["dist"])
      stats["max_distance_nmi"] = max(lastx["dist"]) // 1852

  return stats

def aggregate():
  global latest
  global mutex

  while True:
    time.sleep(60)
    stats = dict()

    with mutex:
      stats_hist.appendleft(copy.deepcopy(latest))
      init()

    last_15min = stats_hist[0]

    for i,d in enumerate(stats_hist):
      if i == 0:
        continue
      last_15min["rssi"] += d["rssi"]
      for j in range(72):
        last_15min["dist"][j] = max(last_15min["dist"][j], d["dist"][j])
      for s in set_stats:
        last_15min[s] |= d[s]
      if i == 3:
        last_5min = last_15min

    stats["last_1min"] = extract(stats_hist[0])
    if len(stats_hist) >= 5:
      stats["last_5min"] = extract(last_5min)
    if len(stats_hist) >= 15:
      stats["last_15min"] = extract(last_15min)

    with open("/run/stats/stats.json", "w") as fout:
      json.dump(stats, fout, indent=4, sort_keys=True)
      fout.write("\n")

    if stats_hist[0]["max_dist"] is not None:
      with open("/run/stats/polar_range.influx", "w") as fout:
        for b, d in enumerate(stats_hist[0]["max_dist"]):
          fout.write("polar_range,bearing=%02d range=%d %d\n" % (b, d, time.time_ns()))

def main():
  global latest
  global mutex

  init()

  try:
    origin = (float(os.environ["LAT"]), float(os.environ["LON"]))
    latest["max_dist"] = [0] * 72
  except:
    LOG("receiver location not set")
    origin = None
    latest["max_dist"] = None

  host = '127.0.0.1'
  port = 30979

  sock = socket.socket()
  sock.connect((host, port))
  fsock = sock.makefile(buffering=1)

  LOG("connected to dump978 JSON output")

  threading.Thread(target=aggregate).start()

  for msg_str in fsock:
    msg = json.loads(msg_str)
    with mutex:
      try:
        parse(msg, origin)
      except KeyError as e:
        LOG("KeyError : %s" % str(e))
        LOG("Offending message JSON : %s" % msg_str)

if __name__ == "__main__":
  main()
