#!/usr/bin/with-contenv python3

# Collect last 1 min stats from dump978 JSON feed

import json
import math
import os
import socket
import sys
import threading
import time

################################################################################
# Shared global stats dictionary and its mutex
################################################################################
raw = {}
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
  global raw
  raw["addr"]                 = set()
  raw["rssi"]                 = list()
  raw["dist"]                 = [0] * 72
  raw["tracks_with_position"] = set()
  raw["airborne_tracks"]      = set()
  raw["ground_tracks"]        = set()
  raw["supersonic_tracks"]    = set()
  raw["adsb_tracks"]          = set()
  raw["tisb_tracks"]          = set()
  raw["surface_tracks"]       = set()
  raw["beacon_tracks"]        = set()
  raw["adsr_tracks"]          = set()

def aggregate(origin):
  global raw
  global mutex

  while True:
    time.sleep(60)
    stats = dict()
    range = list()

    with mutex:
      stats["strong_messages"]      = sum([1 if r > -3.0 else 0 for r in raw["rssi"]])
      stats["total_messages"]       = len(raw["rssi"])
      stats["total_tracks"]         = len(raw["addr"])
      stats["tracks_with_position"] = len(raw["tracks_with_position"])
      stats["airborne_tracks"]      = len(raw["airborne_tracks"])
      stats["ground_tracks"]        = len(raw["ground_tracks"])
      stats["supersonic_tracks"]    = len(raw["supersonic_tracks"])
      stats["adsb_tracks"]          = len(raw["adsb_tracks"])
      stats["tisb_tracks"]          = len(raw["tisb_tracks"])
      stats["surface_tracks"]       = len(raw["surface_tracks"])
      stats["beacon_tracks"]        = len(raw["beacon_tracks"])
      stats["adsr_tracks"]          = len(raw["adsr_tracks"])

      if len(raw["rssi"]) > 0:
        stats["peak_rssi"] = max(raw["rssi"])
        stats["avg_rssi"] = sum(raw["rssi"])/len(raw["rssi"])

        if origin is not None:
          range = raw["max_dist"]
          stats["max_distance_m"] = max(raw["dist"])
          stats["max_distance_nmi"] = max(raw["dist"]) // 1852

      init()

    with open("/run/stats/stats.json", "w") as fout:
      json.dump(stats, fout, indent=4, sort_keys=True)
      fout.write("\n")

    with open("/run/stats/polar_range.influx", "w") as fout:
      for b, d in enumerate(range):
        fout.write("polar_range,bearing=%02d range=%d %d\n" % (b, d, time.time_ns()))

def main():
  global raw
  global mutex

  init()
  raw["max_dist"] = [0] * 72

  try:
    origin = (float(os.environ["LAT"]), float(os.environ["LON"]))
  except:
    LOG("receiver location not set")
    origin = None

  host = '127.0.0.1'
  port = 30979

  sock = socket.socket()
  sock.connect((host, port))
  fsock = sock.makefile(buffering=1)

  LOG("connected to dump978 JSON output")

  threading.Thread(target=aggregate, args=(origin,)).start()

  for msg_str in fsock:
    msg = json.loads(msg_str)
    with mutex:
      try:
        raw["addr"].add(msg["address"])
        raw["rssi"].append(msg["metadata"]["rssi"])

        try:
          if msg["airground_state"] == "ground":
            raw["ground_tracks"].add(msg["address"])
          elif msg["airground_state"] == "airborne":
            raw["airborne_tracks"].add(msg["address"])
          elif msg["airground_state"] == "supersonic":
            raw["supersonic_tracks"].add(msg["address"])
        except KeyError:
          pass

        try:
          if "adsb" in msg["address_qualifier"]:
            raw["adsb_tracks"].add(msg["address"])
          elif "tisb" in msg["address_qualifier"]:
            raw["tisb_tracks"].add(msg["address"])
          elif "vehicle" == msg["address_qualifier"]:
            raw["vehicle_tracks"].add(msg["address"])
          elif "fixed_beacon" == msg["address_qualifier"]:
            raw["beacon_tracks"].add(msg["address"])
          elif "adsr_other" == msg["address_qualifier"]:
            raw["adsr_tracks"].add(msg["address"])
        except KeyError:
          pass

        try:
          pos = (float(msg["position"]["lat"]), float(msg["position"]["lon"]))
          raw["tracks_with_position"].add(msg["address"])
          if origin is not None:
            dist, brng = gps_dist(origin, pos)
            raw["dist"][brng] = max(dist, raw["dist"][brng])
            raw["max_dist"][brng] = max(dist, raw["max_dist"][brng])
        except KeyError:
          pass
      except KeyError as e:
        LOG("Exception message : %s" % str(e))
        LOG("Offending JSON : %s" % msg_str)

if __name__ == "__main__":
  main()
