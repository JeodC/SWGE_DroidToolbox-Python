# Droid Toolbox (Python)
This python package is used to control Galaxy's Edge droids with Bluetooth LE. It's a work in progress port of [droid toolbox](https://github.com/ruthsarian/Droid-Toolbox/blob/main/Droid-Toolbox.ino) by Ruthsarian.

## Dependencies
You need bleak and dbus-fast to connect to droids. `pip download` them and unzip them to the deps folder. For convenience they are included in the repository.

## Usage
Because Windows is more complex and because Linux is easier to work with, this python script will only run in Linux. It was tested with an AYN Thor handheld running Linux AARCH64. By using this script, the Thor becomes a portable beacon.

Run the script with `python main.py` and the script will do a brief check for bluetooth capability. You will then come to the menu where you can scan for droids, emit a beacon, or connect to a droid.

#### Scanning
In scanning mode, the script finds all bluetooth devices with the name `DROID` and checks their Manufacturer ID for the magic Disney byte. If it's a match, the script fetches info with bluetoothctl to grab the droid's Faction and Personality.

#### Beacons
In beacons mode, the bluetooth device will advertise a location of your choosing or pretend to be another droid. The file `dicts.py` stores data for all beacon types and has comments explaining how droids work in response.

#### Connections
You can connect to droids either from the scan menu or from the connection menu, which is populated with saved droids. After pairing with a droid, you can explore commands like audio playback and scripts.
