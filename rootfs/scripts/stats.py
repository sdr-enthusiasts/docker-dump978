#!/usr/bin/with-contenv python3

from abc import ABCMeta, abstractmethod
import collections
from copy import deepcopy
import json
import logging
from logging import info, debug, warning, exception
import math
from os import environ
import socket
from threading import Lock, Thread
import time


###############################################################################
# Classes for various types of statistics
###############################################################################

class BaseStatistic(metaclass=ABCMeta):
    """Defines an abstract base class for a single statistic to collect over time"""

    @staticmethod
    def extract(msg, keys):
        """Extract a key, list of keys, nested key, or list of nested keys from a dictionary"""
        try:
            if keys is None:
                return msg
            if type(keys) is str:
                """Single value"""
                return msg[keys]
            if type(keys) is tuple:
                """Single nested value"""
                val = msg
                for k in keys:
                    val = val[k]
                return val
            if type(keys) is list:
                """Multiple values"""
                out = []
                for k in keys:
                    out.append(BaseStatistic.extract(msg, k))
                return out
        except KeyError as e:
            debug("Couldn't parse keys %s in JSON message" % str(keys))
            debug("%s" % msg)
            raise e

    def __init__(self, name):
        self.name = name
        self.initialize()

    @abstractmethod
    def initialize(self):
        pass

    @abstractmethod
    def parse(self, msg):
        pass

    @abstractmethod
    def get(self):
        pass

    @abstractmethod
    def aggregate(self, new):
        pass


class AverageStatistic(BaseStatistic):
    """Used for statistics that measure an average value over time"""

    def __init__(self, name, key):
        self._key = key
        super().__init__(name)

    def initialize(self):
        self._sum = 0
        self._count = 0

    def parse(self, msg):
        try:
            self._sum += float(self.extract(msg, self._key))
            self._count += 1
        except KeyError:
            pass

    def get(self):
        return None if self._count == 0 else self._sum / self._count

    def aggregate(self, new):
        self._sum += new._sum
        self._count += new._count


class CountStatistic(BaseStatistic):
    """Used for statistics that count occurences over time"""

    def __init__(self, name, key=None, test=None):
        self._key = key
        self._test = test
        super().__init__(name)

    def initialize(self):
        self._count = 0

    def parse(self, msg):
        if self._key is None:
            self._count += 1
        else:
            try:
                val = self.extract(msg, self._key)
                if self._test is None:
                    self._count += 1
                elif type(self._test) is str and self._test in val:
                    self._count += 1
                elif callable(self._test) and self._test(val):
                    self._count += 1
            except KeyError:
                pass

    def get(self):
        return self._count

    def aggregate(self, new):
        self._count += new._count


class MaxStatistic(BaseStatistic):
    """Used for statistics that measure a maximum value over time"""

    def __init__(self, name, key):
        self._key = key
        super().__init__(name)

    def initialize(self):
        self._max = None

    def parse(self, msg):
        try:
            val = float(self.extract(msg, self._key))
            if self._max is None:
                self._max = val
            else:
                self._max = max(self._max, val)
        except KeyError:
            pass

    def get(self):
        return self._max

    def aggregate(self, new):
        if self._max is None:
            self._max = new._max
        elif new._max is not None:
            self._max = max(self._max, new._max)


class MinStatistic(BaseStatistic):
    """Used for statistics that measure a minimum value over time"""

    def __init__(self, name, key):
        self._key = key
        super().__init__(name)

    def initialize(self):
        self._min = None

    def parse(self, msg):
        try:
            val = float(self.extract(msg, self._key))
            if self._min is None:
                self._min = val
            else:
                self._min = min(self._min, val)
        except KeyError:
            pass

    def get(self):
        return self._min

    def aggregate(self, new):
        if self._min is None:
            self._min = new._min
        elif new._min is not None:
            self._min = min(self._min, new._min)


class RangeStatistic(BaseStatistic):
    """Used for statistics that measure maximum range value over time"""

    @staticmethod
    def gps_dist(home, destination):
        """Meters and angle between two coordinates"""

        lat1, lon1 = home
        lat2, lon2 = destination
        radius = 6371000  # meters - change this to change the output distance units

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

        return round(dist), brng

    def __init__(self, name, origin):
        self._origin = origin
        super().__init__(name)

    def initialize(self):
        self._range = [0] * 72

    def parse(self, msg):
        try:
            pos = self.extract(msg, [("position", "lat"), ("position", "lon")])
            dist, brng = self.gps_dist(self._origin, pos)
            bucket = round(brng / 5) % 72
            self._range[bucket] = max(dist, self._range[bucket])
        except KeyError:
            pass

    def get(self):
        return max(self._range)

    def aggregate(self, new):
        for i, v in enumerate(self._range):
            self._range[i] = max(v, new._range[i])


class UniqueStatistic(BaseStatistic):
    """Used for statistics that count unique occurences over time"""

    def __init__(self, name, key=None, test=None):
        self._key = key
        self._test = test
        super().__init__(name)

    def initialize(self):
        self._ids = set()

    def parse(self, msg):
        try:
            val = self.extract(msg, self._key)
            if self._test is None:
                self._ids.add(msg["address"])
            elif type(self._test) is str and self._test in val:
                self._ids.add(msg["address"])
            elif callable(self._test) and self._test(val):
                self._ids.add(msg["address"])
        except KeyError:
            pass

    def get(self):
        return len(self._ids)

    def aggregate(self, new):
        self._ids |= new._ids


class PeriodStatistics:
    """A collection of statistics over time"""

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
# Functions
###############################################################################

def aggregate(raw_lock, raw_latest, json_lock, json_latest, polar_range):
    """Aggregate stats and write output files"""

    try:
        with json_lock:
            aggregate.history.appendleft(deepcopy(json_latest))
            json_latest.initialize()
    except AttributeError:
        aggregate.history = collections.deque([], 15)
        return

    with raw_lock:
        aggregate.history[0].aggregate(deepcopy(raw_latest))
        raw_latest.initialize()

    last_15min = deepcopy(aggregate.history[0])

    for i, d in enumerate(aggregate.history):
        if i == 0:
            continue
        last_15min.aggregate(d)
        if i == 4:
            last_5min = deepcopy(last_15min)
    out = dict()

    out["last_1min"] = aggregate.history[0].to_dict()
    if len(aggregate.history) >= 5:
        out["last_5min"] = last_5min.to_dict()
    if len(aggregate.history) >= 15:
        out["last_15min"] = last_15min.to_dict()

    with open("/run/stats/stats.json", "w") as f:
        json.dump(out, f, indent=4, sort_keys=True)
        f.write("\n")

    if polar_range is not None:
        polar_range.aggregate(aggregate.history[0].get("max_distance_m"))
        with open("/run/stats/polar_range.influx", "w") as fout:
            for b, d in enumerate(polar_range._range):
                fout.write("polar_range,bearing=%02d range=%d %d\n" % (b, d, time.time_ns()))


def parse_json(json_lock, json_latest):
    """Parse decoded JSON messages"""

    while True:
        try:
            json_sock = socket.socket()
            json_sock.connect(("127.0.0.1", 30979))
            info("connected to dump978 decoded JSON output")

            with json_sock.makefile(buffering=1) as fjson:
                for msg in fjson:
                    with json_lock:
                        json_latest.parse(json.loads(msg))
        except Exception:
            exception("JSON socket thread failed!")


def parse_raw(raw_lock, raw_latest):
    """Parse raw UAT messages"""

    while True:
        try:
            raw_sock = socket.socket()
            raw_sock.connect(("127.0.0.1", 30978))
            info("connected to dump978 raw output")

            with raw_sock.makefile(buffering=1) as fraw:
                for msg in fraw:
                    with raw_lock:
                        try:
                            rssi_begin = msg.index("rssi=") + 5
                            rssi_end = rssi_begin + msg[rssi_begin:].index(";")
                            raw_latest.parse({"rssi": float(msg[rssi_begin:rssi_end])})
                        except ValueError:
                            debug("Did not find RSSI in raw message:\n%s" % msg)
        except Exception:
            exception("Raw socket thread failed!")


def main():
    # Change the argument to adjust logging output
    logging.basicConfig(level=logging.INFO)

    raw_lock = Lock()
    raw_latest = PeriodStatistics()
    raw_latest.add(CountStatistic("total_raw_messages"))
    raw_latest.add(CountStatistic("strong_raw_messages", key="rssi", test=lambda v: float(v) > -3.0))
    raw_latest.add(AverageStatistic("avg_raw_rssi", key="rssi"))
    raw_latest.add(MaxStatistic("peak_raw_rssi", key="rssi"))
    raw_latest.add(MinStatistic("min_raw_rssi", key="rssi"))

    json_lock = Lock()
    json_latest = PeriodStatistics()
    json_latest.add(CountStatistic("total_accepted_messages"))
    json_latest.add(CountStatistic("strong_accepted_messages", key=("metadata", "rssi"), test=lambda v: float(v) > -3.0))
    json_latest.add(AverageStatistic("avg_accepted_rssi", key=("metadata", "rssi")))
    json_latest.add(MaxStatistic("peak_accepted_rssi", key=("metadata", "rssi")))
    json_latest.add(MinStatistic("min_accepted_rssi", key=("metadata", "rssi")))
    json_latest.add(UniqueStatistic("total_tracks"))
    json_latest.add(UniqueStatistic("tracks_with_position", test=lambda m: "position" in m))
    json_latest.add(UniqueStatistic("airborne_tracks", key="airground_state", test="airborne"))
    json_latest.add(UniqueStatistic("ground_tracks", key="airground_state", test="ground"))
    json_latest.add(UniqueStatistic("supersonic_tracks", key="airground_state", test="supersonic"))
    json_latest.add(UniqueStatistic("adsb_tracks", key="address_qualifier", test="adsb"))
    json_latest.add(UniqueStatistic("tisb_tracks", key="address_qualifier", test="tis"))
    json_latest.add(UniqueStatistic("vehicle_tracks", key="address_qualifier", test="vehicle"))
    json_latest.add(UniqueStatistic("beacon_tracks", key="address_qualifier", test="beacon"))
    json_latest.add(UniqueStatistic("adsr_tracks", key="address_qualifier", test="adsr"))

    try:
        origin = (float(environ["LAT"]), float(environ["LON"]))
        max_dist = RangeStatistic("max_distance_m", origin)
        json_latest.add(max_dist)
        polar_range = deepcopy(max_dist)
    except KeyError:
        polar_range = None
        warning("receiver location not set")

    Thread(target=parse_raw, args=(raw_lock, raw_latest)).start()
    Thread(target=parse_json, args=(json_lock, json_latest)).start()

    while True:
        aggregate(raw_lock, raw_latest, json_lock, json_latest, polar_range)
        time.sleep(60)


if __name__ == "__main__":
    main()
