# totem-battery

Reads and displays battery levels for both halves of the [Totem](https://github.com/GEIGEIGEIST/TOTEM) split keyboard over Bluetooth on macOS.
<img width="584" height="34" alt="image" src="https://github.com/user-attachments/assets/51be34d0-ca4a-482f-bd6b-8e41fb121a05" />


## Requirements

- macOS (uses CoreBluetooth via PyObjC)
- Totem keyboard connected via Bluetooth
- Python dependencies: `pip install -r requirements.txt`

## Firmware prerequisite

Your ZMK firmware must include these settings in `config/totem.conf`:

```
CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_PROXY=y
CONFIG_ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_FETCHING=y
```

Without these, only the left (central) half will report a battery level.

## Menubar app

Displays live battery levels in the macOS menubar, refreshing automatically.

```
python menubar.py
```

The menubar shows `⌨️ L:82% R:67%`. Click it to refresh manually or change the refresh interval (default: every 5 minutes). The selected interval persists across restarts.

**Note:** On first launch, macOS will prompt to allow Bluetooth access for Python. Click Allow.

**To launch at login:** Add a Login Item in System Settings → General → Login Items pointing to a shell script that runs `python /path/to/menubar.py`.

## CLI

For a one-shot reading in the terminal:

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

macOS blocks BLE scans from returning already-connected HID devices, so both scripts use CoreBluetooth directly via PyObjC (`CBCentralManager.retrieveConnectedPeripheralsWithServices_`) to access the already-connected keyboard. It reads the GATT Battery Service (`0x180F`) and Battery Level characteristic (`0x2A19`) from the central, which proxies both halves when the ZMK config flags above are enabled.
