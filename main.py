import os
import shutil

from bluetoothctl import BluetoothCtl
from beacon import DroidController, beacon_menu
from scan import scanning_menu

def main_menu(droid: DroidController):
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        print(f"{'--- DROID TOOLBOX MAIN MENU--- '}")
        print("\n1. Scanning")
        print("2. Beacons")
        print("Q. Quit")
        choice = input("\nSelect > ").upper()
        if choice == '1':
            scanning_menu(droid)
        elif choice == '2':
            beacon_menu(droid)
        elif choice == 'Q':
            break

def main():
    # Check for bluetoothctl
    if shutil.which("bluetoothctl") is None:
        print("ERROR: bluetoothctl not found. This program requires Linux with BlueZ.")
        input("Press any key to quit...")
        return

    # Try to initialize BluetoothCtl
    try:
        bt = BluetoothCtl()
    except FileNotFoundError:
        print("ERROR: Failed to initialize BluetoothCtl.")
        input("Press any key to quit...")
        return

    droid = DroidController(bt)
    try:
        main_menu(droid)
    finally:
        droid.shutdown()

if __name__ == "__main__":
    main()
