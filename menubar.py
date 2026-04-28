"""
Totem keyboard battery monitor — macOS menubar app.

Usage:
    python menubar.py

Requires the same ZMK firmware config as battery.py.
"""

import json
import os
from datetime import datetime

import objc
import CoreBluetooth
import rumps

from totem_ble import BATTERY_SVC, BATTERY_CHAR, USER_DESC, DEVICE_NAME, LABEL_MAP

CONFIG_PATH = os.path.expanduser("~/.config/totem-battery/config.json")
DEFAULT_INTERVAL = 300  # seconds

INTERVAL_OPTIONS = [
    ("1 minute",  60),
    ("5 minutes", 300),
    ("15 minutes", 900),
    ("30 minutes", 1800),
    ("1 hour",    3600),
]

_CBProto  = objc.protocolNamed("CBCentralManagerDelegate")
_CBPProto = objc.protocolNamed("CBPeripheralDelegate")


class _MBPeripheralDelegate(objc.lookUpClass("NSObject"), protocols=[_CBPProto]):
    def peripheral_didDiscoverServices_(self, p, err):
        for svc in p.services():
            if svc.UUID().UUIDString() == BATTERY_SVC:
                p.discoverCharacteristics_forService_(None, svc)

    def peripheral_didDiscoverCharacteristicsForService_error_(self, p, svc, err):
        for c in svc.characteristics():
            if c.UUID().UUIDString() != BATTERY_CHAR:
                continue
            if not any(bc == c for bc in self.app._battery_chars):
                self.app._battery_chars.append(c)
                self.app._pending_results.append(None)
            p.readValueForCharacteristic_(c)
            if not any(lc == c for lc in self.app._label_chars):
                p.discoverDescriptorsForCharacteristic_(c)

    def peripheral_didDiscoverDescriptorsForCharacteristic_error_(self, p, c, err):
        for d in (c.descriptors() or []):
            if d.UUID().UUIDString() == USER_DESC:
                p.readValueForDescriptor_(d)

    def peripheral_didUpdateValueForCharacteristic_error_(self, p, c, err):
        if c.UUID().UUIDString() != BATTERY_CHAR or not c.value():
            return
        level = c.value().bytes()[0]
        for i, bc in enumerate(self.app._battery_chars):
            if bc == c:
                self.app._pending_results[i] = level
                break
        if all(v is not None for v in self.app._pending_results):
            self.app._update_title()

    def peripheral_didUpdateValueForDescriptor_error_(self, p, d, err):
        if d.UUID().UUIDString() != USER_DESC or not d.value():
            return
        val = d.value()
        label = val if isinstance(val, str) else bytes(val).decode("utf-8", errors="replace")
        label = label.strip()
        c = d.characteristic()
        for i, bc in enumerate(self.app._battery_chars):
            if bc == c:
                self.app._labels[i] = LABEL_MAP.get(label, label) if label else "Left"
                self.app._label_chars.append(c)
                break
        if all(v is not None for v in self.app._pending_results):
            self.app._update_title()


class _MBCentralDelegate(objc.lookUpClass("NSObject"), protocols=[_CBProto]):
    def centralManagerDidUpdateState_(self, mgr):
        if mgr.state() == 5:
            self.app._on_bluetooth_ready()

    def centralManager_didConnectPeripheral_(self, mgr, p):
        self.app._connected = True
        p.setDelegate_(self.pd)
        if self.app._battery_chars:
            self.app._pending_results = [None] * len(self.app._battery_chars)
            for c in self.app._battery_chars:
                p.readValueForCharacteristic_(c)
        else:
            self.app._pending_results = []
            p.discoverServices_([CoreBluetooth.CBUUID.UUIDWithString_(BATTERY_SVC)])

    def centralManager_didDisconnectPeripheral_error_(self, mgr, p, err):
        self.app._connected = False
        self.app._battery_chars = []
        self.app._labels = {}
        self.app._label_chars = []


_pd = _MBPeripheralDelegate.alloc().init()
_cd = _MBCentralDelegate.alloc().init()


def _load_interval():
    try:
        with open(CONFIG_PATH) as f:
            return int(json.load(f).get("refresh_interval_seconds", DEFAULT_INTERVAL))
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError):
        return DEFAULT_INTERVAL


def _save_interval(seconds):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump({"refresh_interval_seconds": seconds}, f)


class TotemBatteryApp(rumps.App):
    def __init__(self):
        super().__init__("totem-battery", title="⌨️ --/--")

        self._connected = False
        self._battery_chars = []
        self._pending_results = []
        self._labels = {}       # {index: label string}
        self._label_chars = []  # chars whose descriptors have been fetched
        self._peripheral = None
        self._interval = _load_interval()

        _pd.app = self
        _cd.app = self
        _cd.pd = _pd

        self._mgr = CoreBluetooth.CBCentralManager.alloc().initWithDelegate_queue_(_cd, None)
        self._refresh_timer = rumps.Timer(self._refresh, self._interval)

        self._status_item = rumps.MenuItem("Not connected")
        self._interval_menu = rumps.MenuItem("Refresh interval")
        self._interval_items = {}
        for label, secs in INTERVAL_OPTIONS:
            item = rumps.MenuItem(label, callback=lambda sender, s=secs: self._set_interval(s))
            item.state = 1 if secs == self._interval else 0
            self._interval_menu.add(item)
            self._interval_items[secs] = item

        self.menu = [
            rumps.MenuItem("Refresh now", callback=self._refresh),
            self._interval_menu,
            None,
            self._status_item,
        ]

    def _on_bluetooth_ready(self):
        self._refresh_timer.start()
        self._refresh()

    def _refresh(self, _=None):
        svc_uuid = CoreBluetooth.CBUUID.UUIDWithString_(BATTERY_SVC)
        peripherals = self._mgr.retrieveConnectedPeripheralsWithServices_([svc_uuid])
        match = next((p for p in peripherals if DEVICE_NAME in (p.name() or "").lower()), None)
        if match is None:
            self.title = "⌨️ --/--"
            self._status_item.title = "Not connected"
            return
        self._peripheral = match
        self._mgr.connectPeripheral_options_(match, None)

    def _update_title(self):
        parts = []
        for i, level in enumerate(self._pending_results):
            if level is None:
                continue
            label = self._labels.get(i, "Left" if i == 0 else "Right")
            short = "L" if label in ("Left", "Central") else "R"
            parts.append(f"{short}:{level}%")
        if parts:
            self.title = "⌨️ " + " ".join(parts)
            now = datetime.now().strftime("%H:%M")
            self._status_item.title = f"Updated {now}"

    def _set_interval(self, seconds):
        self._interval = seconds
        self._refresh_timer.stop()
        self._refresh_timer = rumps.Timer(self._refresh, seconds)
        self._refresh_timer.start()
        _save_interval(seconds)
        for secs, item in self._interval_items.items():
            item.state = 1 if secs == seconds else 0


if __name__ == "__main__":
    TotemBatteryApp().run()
