"""
Read Totem keyboard battery levels directly via GATT using CoreBluetooth.

Requires the following enabled in your ZMK firmware (config/totem.conf):

    CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_PROXY=y
    CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_FETCHING=y

Without these, only the left (central) half will report a battery level.
"""

import sys
import objc
import CoreBluetooth
from Foundation import NSRunLoop, NSDate

BATTERY_SVC  = "180F"
BATTERY_CHAR = "2A19"
USER_DESC    = "2901"
DEVICE_NAME  = "totem"

results = []

Proto  = objc.protocolNamed("CBCentralManagerDelegate")
PProto = objc.protocolNamed("CBPeripheralDelegate")


class PeripheralDelegate(objc.lookUpClass("NSObject"), protocols=[PProto]):
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
            results.append({"char": c, "level": level, "label": None})

    def peripheral_didUpdateValueForDescriptor_error_(self, p, d, err):
        if d.UUID().UUIDString() == USER_DESC and d.value():
            val = d.value()
            label = val if isinstance(val, str) else bytes(val).decode("utf-8", errors="replace")
            label = label.strip()
            for r in results:
                if d.characteristic() == r["char"]:
                    r["label"] = label


class CentralDelegate(objc.lookUpClass("NSObject"), protocols=[Proto]):
    def centralManagerDidUpdateState_(self, mgr):
        pass

    def centralManager_didConnectPeripheral_(self, mgr, p):
        p.setDelegate_(pd)
        p.discoverServices_([CoreBluetooth.CBUUID.UUIDWithString_(BATTERY_SVC)])


def spin(seconds):
    for _ in range(int(seconds / 0.1)):
        NSRunLoop.mainRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))


pd = PeripheralDelegate.alloc().init()
cd = CentralDelegate.alloc().init()
mgr = CoreBluetooth.CBCentralManager.alloc().initWithDelegate_queue_(cd, None)

spin(2)

if mgr.state() != 5:
    print("Bluetooth is not available or not powered on.", file=sys.stderr)
    sys.exit(1)

svc_uuid = CoreBluetooth.CBUUID.UUIDWithString_(BATTERY_SVC)
peripherals = mgr.retrieveConnectedPeripheralsWithServices_([svc_uuid])
match = next((p for p in peripherals if DEVICE_NAME in (p.name() or "").lower()), None)

if match is None:
    print(f"Totem keyboard not found. Make sure it is connected via Bluetooth.", file=sys.stderr)
    sys.exit(1)

print(f"{match.name()}")
mgr.connectPeripheral_options_(match, None)
spin(8)

if not results:
    print("No battery data received.", file=sys.stderr)
    sys.exit(1)

# Deduplicate by characteristic identity (in case of duplicate callbacks).
seen = {}
for r in results:
    seen[id(r["char"])] = r
unique = list(seen.values())

LABEL_MAP = {
    "Peripheral 0": "Right",
}

for r in unique:
    raw = r["label"]
    label = LABEL_MAP.get(raw, raw) if raw else "Left"
    print(f"  {label}: {r['level']}%")

if len(unique) == 1:
    print(
        "\n  Only one battery level reported. Enable both settings in config/totem.conf:\n"
        "    CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_PROXY=y\n"
        "    CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_FETCHING=y\n"
        "  Then rebuild and flash your firmware."
    )
