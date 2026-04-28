# totem-battery

Reads and displays battery levels for both halves of the [Totem](https://github.com/GEIGEIGEIST/TOTEM) split keyboard over Bluetooth on macOS.

## Requirements

- macOS (uses CoreBluetooth via PyObjC — no extra packages needed beyond the standard macOS Python toolchain)
- Totem keyboard connected via Bluetooth

## Firmware prerequisite

Your ZMK firmware must include these settings in `config/totem.conf`:

```
CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_PROXY=y
CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_FETCHING=y
```

Without these, only the left (central) half will report a battery level.

## Usage

Make sure the Totem is connected via Bluetooth, then run:

```
python battery.py
```

Expected output:

```
TOTEM
  Left: 82%
  Right: 67%
```

## How it works

macOS blocks BLE scans from returning already-connected HID devices, so the script uses CoreBluetooth directly via PyObjC (`CBCentralManager.retrieveConnectedPeripheralsWithServices_`) to access the already-connected keyboard. It reads the GATT Battery Service (`0x180F`) and Battery Level characteristic (`0x2A19`) from the central, which proxies both halves when the ZMK config flags above are enabled.
