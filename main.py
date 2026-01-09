import os
import shutil
import sys

from bluetoothctl import BluetoothCtl
from ui import DroidUI

# --- PATH SETUP ---
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(script_dir, "deps"))

def main():
    # 1. Check for system dependencies
    if shutil.which("bluetoothctl") is None:
        print("ERROR: bluetoothctl not found. This program requires Linux with BlueZ.")
        return

    # 2. Initialize Hardware Controller
    try:
        # We only need the raw Bluetooth controller here
        bt = BluetoothCtl()
    except Exception as e:
        print(f"ERROR: Failed to initialize BluetoothCtl: {e}")
        return

    # 3. Initialize the UI (This class handles Beacon and Scanner internally)
    interface = DroidUI(bt)

    # 4. Main Program Loop
    try:
        while True:
            interface.clear()
            print("--- DROID TOOLBOX MAIN MENU ---")
            print("\n1. Droid Scan")
            print("2. Emit Beacon")
            print("3. Saved Droids")
            print("Q. Quit")
            
            choice = input("\nSelect > ").upper()
            
            if choice == '1':
                interface.scanning_menu()
            elif choice == '2':
                interface.beacon_main_menu()
            elif choice == '3':
                interface.favorites_menu()
            elif choice == 'Q':
                break
    except Exception as e:
        print(f"FATAL ERROR: {e}")
    finally:
        # Ensure we stop any active advertising and close the socket
        bt.stop_advertising()
        bt.close()

if __name__ == "__main__":
    main()