# Droid Toolbox (Python)
This python package is used to control Galaxy's Edge droids with Bluetooth LE. It's a work in progress port of [droid toolbox](https://github.com/ruthsarian/Droid-Toolbox/blob/main/Droid-Toolbox.ino) by Ruthsarian, created to be used by linux handheld devices such as the [Anbernic RG40XXH](https://anbernic.com/products/rg40xx-h).

## Dependencies
You need bleak and dbus-fast to connect to droids. For convenience they are included in the repository. If you are using muOS you will need the [bltMuos](https://github.com/nvcuong1312/bltMuos/releases) application installed.

## Usage
Run the script over ssh with `python main.py` and the script will do a brief check for bluetooth capability. You will then come to the menu where you can scan for droids, emit a beacon, or connect to a droid. When a release is prepared, a proper launchscript (`.sh` file) will be added so the application can be launched directly by the device.

### Scanning
In scanning mode, the script finds all bluetooth devices with the name `DROID` and checks their Manufacturer ID for the magic Disney byte. If it's a match, the script fetches info with bluetoothctl, if possible, to grab the droid's Faction and Personality. You can add a droid to your favorites list to remember it.

### Beacons
In beacons mode, the bluetooth device will advertise a location of your choosing or pretend to be another droid. The file `dicts.py` stores data for all beacon types and has comments explaining how droids work in response.

### Connections
You can connect to droids either from the scan menu or from the connection menu, which is populated with saved droids. After pairing with a droid, you can explore commands like audio playback and scripts.

## Planned Features
[ ] Prettify UI with Aurebesh font decorations and theme options (change color schemes)
[ ] Remotely drive your droid
[ ] Use an on-screen keyboard to type in names for favorite droids
