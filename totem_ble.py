"""
Blocking BLE battery read for the Totem split keyboard. Used by battery.py (CLI).
Not suitable for use inside an already-running event loop.
"""

import objc
import CoreBluetooth
from Foundation import NSRunLoop, NSDate

BATTERY_SVC  = "180F"
BATTERY_CHAR = "2A19"
USER_DESC    = "2901"
DEVICE_NAME  = "totem"

LABEL_MAP = {
    "Peripheral 0": "Right",
}

_Proto  = objc.protocolNamed("CBCentralManagerDelegate")
_PProto = objc.protocolNamed("CBPeripheralDelegate")

_results = []


class _PeripheralDelegate(objc.lookUpClass("NSObject"), protocols=[_PProto]):
    def peripheral_didDiscoverServices_(self, p, err):
        for svc in p.services():
            if svc.UUID().UUIDString() == BATTERY_SVC:
                p.discoverCharacteristics_forService_(None, svc)

    def peripheral_didDiscoverCharacteristicsForService_error_(self, p, svc, err):
        for c in svc.characteristics():
            if c.UUID().UUIDString() == BATTERY_CHAR:
                p.readValueForCharacteristic_(c)
                p.discoverDescriptorsForCharacteristic_(c)

    def peripheral_didDiscoverDescriptorsForCharacteristic_error_(self, p, c, err):
        for d in (c.descriptors() or []):
            if d.UUID().UUIDString() == USER_DESC:
                p.readValueForDescriptor_(d)

    def peripheral_didUpdateValueForCharacteristic_error_(self, p, c, err):
        if c.UUID().UUIDString() == BATTERY_CHAR and c.value():
            level = c.value().bytes()[0]
            _results.append({"char": c, "level": level, "label": None})

    def peripheral_didUpdateValueForDescriptor_error_(self, p, d, err):
        if d.UUID().UUIDString() == USER_DESC and d.value():
            val = d.value()
            label = val if isinstance(val, str) else bytes(val).decode("utf-8", errors="replace")
            label = label.strip()
            for r in _results:
                if d.characteristic() == r["char"]:
                    r["label"] = label


class _CentralDelegate(objc.lookUpClass("NSObject"), protocols=[_Proto]):
    def centralManagerDidUpdateState_(self, mgr):
        pass

    def centralManager_didConnectPeripheral_(self, mgr, p):
        p.setDelegate_(_pd)
        p.discoverServices_([CoreBluetooth.CBUUID.UUIDWithString_(BATTERY_SVC)])


_pd = _PeripheralDelegate.alloc().init()
_cd = _CentralDelegate.alloc().init()


def _spin(seconds):
    for _ in range(int(seconds / 0.1)):
        NSRunLoop.mainRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))


def read_batteries(timeout: float = 8.0) -> list[dict]:
    """
    Returns [{"label": "Left", "level": 82}, ...].
    Returns [] if keyboard not found or no data received.
    Raises RuntimeError if Bluetooth is off.
    """
    global _results
    _results = []

    mgr = CoreBluetooth.CBCentralManager.alloc().initWithDelegate_queue_(_cd, None)
    _spin(2)

    if mgr.state() != 5:
        raise RuntimeError("Bluetooth is not available or not powered on.")

    svc_uuid = CoreBluetooth.CBUUID.UUIDWithString_(BATTERY_SVC)
    peripherals = mgr.retrieveConnectedPeripheralsWithServices_([svc_uuid])
    match = next((p for p in peripherals if DEVICE_NAME in (p.name() or "").lower()), None)

    if match is None:
        return []

    mgr.connectPeripheral_options_(match, None)
    _spin(timeout)

    seen = {}
    for r in _results:
        seen[id(r["char"])] = r
    unique = list(seen.values())

    return [
        {
            "label": LABEL_MAP.get(r["label"], r["label"]) if r["label"] else "Left",
            "level": r["level"],
        }
        for r in unique
    ]
