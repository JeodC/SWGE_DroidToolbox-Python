# Droid Toolbox (Python)
This python package is used to control Galaxy's Edge droids with Bluetooth LE. It's a work in progress port of [droid toolbox](https://github.com/ruthsarian/Droid-Toolbox/blob/main/Droid-Toolbox.ino) by Ruthsarian.

## Usage
Because Windows is more complex and because Linux is easier to work with, this python script will only run in Linux. It was tested with an AYN Thor handheld running Linux AARCH64. By using this script, the Thor becomes a portable beacon.

Run the script with `python main.py` and the script will do a brief check for bluetooth capability. You will then come to the menu where you can scan for droids or choose to advertise beacons.

#### Scanning
In scanning mode, the script finds all bluetooth devices with the name `DROID` and checks their Manufacturer ID for the magic Disney byte. If it's a match, the script fetches info with bluetoothctl to grab the droid's Faction and Personality.

#### Beacons
In beacons mode, the bluetooth device will advertise a location of your choosing or pretend to be another droid. The file `dicts.py` stores data for all beacon types and has comments explaining how droids work in response.
