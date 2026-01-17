# Droid Toolbox (Python)
This python package is used to control Galaxy's Edge droids with Bluetooth LE. It's a work in progress port of [droid toolbox](https://github.com/ruthsarian/Droid-Toolbox/blob/main/Droid-Toolbox.ino) by Ruthsarian, created to be used by linux handheld devices such as the [Anbernic RG40XXH](https://anbernic.com/products/rg40xx-h).

## Dependencies
You need bleak and dbus-fast to connect to droids. For convenience they are included in the repository. If you are using muOS you will need the [bltMuos](https://github.com/nvcuong1312/bltMuos/releases) application installed.

<div align="center">
<img width="640" height="480" alt="droidtoolbox-main" src="https://github.com/user-attachments/assets/b16a2a81-6358-479b-a467-5229dafe0264" />
</div>

## Usage
If using muOS, install [bltMuos](https://github.com/nvcuong1312/bltMuos/releases) and then install Droid Toolbox. You must be using muOS 2508.x Goose.

If using other systems, have PortMaster installed and then put the zip release in the `ports/autoinstall` folder.

### Scanning
In scanning mode, the script finds all bluetooth devices with the name `DROID` and checks their Manufacturer ID for the magic Disney byte. If it's a match, the script fetches info with bluetoothctl, if possible, to grab the droid's Faction and Personality. You can add a droid to your favorites list to remember it.

### Beacons
In beacons mode, the bluetooth device will advertise a location of your choosing or pretend to be another droid. The file `dicts.py` stores data for all beacon types and has comments explaining how droids work in response.

### Connections
You can connect to droids either from the scan menu or from the connection menu, which is populated with saved droids. After pairing with a droid, you can explore commands like audio playback and scripts.

## Planned Features
[ ] Prettify UI with Aurebesh font decorations and theme options (change color schemes)  
[x] Remotely drive your droid  
[ ] Use an on-screen keyboard to type in names for favorite droids  

## Credits
Massive thanks to Ruthsarian and their extensive documentation and research on SWGE Droids!
Fonts originate from [Unfiction.GitHub.IO](https://unfiction.github.io/resources/fonts/GEFonts.html)
