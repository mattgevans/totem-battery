"""
Read Totem keyboard battery levels directly via GATT using CoreBluetooth.

Requires the following enabled in your ZMK firmware (config/totem.conf):

    CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_PROXY=y
    CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_FETCHING=y

Without these, only the left (central) half will report a battery level.
"""

import sys
from totem_ble import read_batteries

try:
    results = read_batteries()
except RuntimeError as e:
    print(e, file=sys.stderr)
    sys.exit(1)

if not results:
    print("Totem keyboard not found. Make sure it is connected via Bluetooth.", file=sys.stderr)
    sys.exit(1)

print("TOTEM")
for r in results:
    print(f"  {r['label']}: {r['level']}%")

if len(results) == 1:
    print(
        "\n  Only one battery level reported. Enable both settings in config/totem.conf:\n"
        "    CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_PROXY=y\n"
        "    CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_FETCHING=y\n"
        "  Then rebuild and flash your firmware."
    )
