#!/usr/bin/env python3
"""
dicts.py - Constants
"""

# Favorites dict -- populated when starting the application
FAVORITES = {}

# Droid signals are extensively documented
# https://docs.google.com/spreadsheets/d/13P_GE6tNYpGvoVUTEQvA3SQzMqpZ-SoiWaTNoJoTV9Q

BEACON_PROTOCOL = {
    "MFG_ID": 0x0183,        # Manufacturer ID
    "DATA_LEN": 0x04,        # The length of the remaining data after the header
    "DROID_HEADER": 0x44,    # This byte is probably a guard in addition to the beacon type, to prevent accidental triggers by unrelated beacons
    "STATUS_FLAG": 0x81,     # 0x01 if droid is not paired with a remote, 0x81 if it is
    "ACTIVE_FLAG": 0x01,     # Possibly a receiver-facing active flag; would allow beacons to be logically enabled/disabled without relying on radio silence
}

BEACON_TYPE = {
    "LOCATION": 0x0A,
    "DROID":    0x03,
}

RSSI_THRESHOLD = {
    "NEAR": 0xBA,    # (-70 dBm): Very close, high signal
    "MID":  0xA6,    # (-90 dBm): Small room/standard distance
    "FAR":  0x9C,    # (-100 dBm): Large room or through light obstruction
    "MAX":  0x8C,    # (-116 dBm): Maximum range before drop-off
}

# LOCATION BEACONS
# - Droids that react to a location beacon will not sleep for 6 hours
# - The first element in each tuple tells the droid which audio group to play from
# - Droids will therefore have different reactions for some areas depending on their faction
# - Third element in each tuple is cooldown timer, multiply by 5 to get cooldown in seconds
# - Droids have a minimum cooldown of 60 seconds between location beacon reactions, 0xFF may be an override
# - Locations mapped: https://galaxysedgetech.epizy.com
LOCATIONS = {
    1: (0x01, "Ronto Roasters", 0x02), # Also emits near other food vendors in the marketplace
    2: (0x02, "Oil Baths", 0x02), # Also called the droid playground; the group of droids behind the depot
    3: (0x03, "Resistance Base", 0x02),
    4: (0x04, "Unknown", 0x02), # Droids react to this location, but it has not been discovered anywhere yet
    5: (0x05, "Droid Depot", 0x02), # Also emits in front of the marketplace
    6: (0x06, "Den of Antiquities", 0x02),
    7: (0x07, "First Order Base", 0x02),
    8: (0x05, "Oga's Droid Detector", 0xFF),
    9: (0x07, "First Order Alert", 0xFF)
}

# DROID PERSONALITIES
# - Emulates the presence of another droid
# - Droids will wait 2 minutes between reactions to droid beacons
# - Droids that have reacted to a location beacon within 2 hours will not react to droid beacons
FACTIONS = {
    "Scoundrel": 0x01,
    "Resistance": 0x05,
    "First Order": 0x09,
}

DROIDS = {
    "Scoundrel": {
        1: {"id": 0x01, "name": "R-Series (Default)"},
        2: {"id": 0x02, "name": "BB-Series (Default)"},
        3: {"id": 0x04, "name": "Gray (U9-C4)"},
        4: {"id": 0x07, "name": "Purple (M5-BZ)"},
        5: {"id": 0x09, "name": "Cyan/Red (CB-23)"}, # CB-23 came with a cyan personality chip, later sold separately as red
        6: {"id": 0x0D, "name": "Blue (R5-D4)"},
        7: {"id": 0x0F, "name": "A-LT Series (Default)"},
        8: {"id": 0x10, "name": "White (Drum Kit)"},
    },
    "Resistance": {
        1: {"id": 0x03, "name": "Blue (R5-D8)"},
        2: {"id": 0x06, "name": "Orange (R4-P17)"},
        3: {"id": 0x0A, "name": "Yellow (CH-33P)"},
        4: {"id": 0x0B, "name": "C-Series (Default)"},
        5: {"id": 0x0C, "name": "D-Unit (Default)"},
        6: {"id": 0x0E, "name": "BD-Unit (Default)"},
        7: {"id": 0x01, "name": "Green (R2-H15)"}, # Bundled with R2-H15 Holiday Droid, sold in 2025
        8: {"id": 0x01, "name": "Orange (SPOOK-E)"}, # Bundled with R-Series panels sold in 2025
    },
    "First Order": {
        1: {"id": 0x05, "name": "Red (0-0-0)"},
        2: {"id": 0x08, "name": "Black (BB-9E)"},
    },
}

# DROID CONNECTIONS
# - To connect to a droid the remote must be turned off
# - The service and characteristics are used to communicate with the droid
SERVICE_UUID = "09b600a0-3e42-41fc-b474-e9c0c8f0c801"

CHARACTERISTICS = {
    "COMMAND": {
        "uuid": "09b600b1-3e42-41fc-b474-e9c0c8f0c801",
        "handle": "0x000e"
    },
    "NOTIFY": {
        "uuid": "09b600b0-3e42-41fc-b474-e9c0c8f0c801",
        "handle": "0x000b"
    }
}

# DROID COMMANDS
# - R-Series and A-LT Series use direct motor control and have a separate set used for scripts
# - BB-Series have a holonomic sphere and use a different logic
COMMANDS = {
    # --- SYSTEM & CONNECTION ---
    "LOGON":           [0x22, 0x20, 0x01, 0x42],
    "PAIRING_LED":     [0x23, 0x00, 0x02, 0x41], # Append 0x01 (On) or 0x00 (Off)
    "AUDIO_BASE":      [0x27, 0x42, 0x0F, 0x44, 0x44, 0x00], # Append GG, CC (GrouipID, ClipID)

    # --- R-SERIES ---
    # Direct Motor Control (Command 0x05), used for raw tank-style steering
    # DM (Direction + Motor) is a single byte:
    # High Nibble (Direction): 0x0=Fwd/Left, 0x8=Rev/Right
    # Low Nibble (Motor ID): 0x0=Left, 0x1=Right, 0x2=Head
    # Add the Nibbles to get the byte
    # Speed: 0x60 (min) to 0xFF (max)
    # !! WARNING !! Motors will NOT stop until a specific stop command is sent
    "MOTOR_DIRECT":    [0x27, 0x00, 0x05, 0x44], # Append Direction, Motor, Speed (usually 0xA0), Ramp-up(x2) (usually 0x012C)
    "MOTOR_STOP_L":    [0x27, 0x00, 0x05, 0x44, 0x00, 0x00, 0x00, 0x00], # Direct stop Left (0x00)
    "MOTOR_STOP_R":    [0x27, 0x00, 0x05, 0x44, 0x01, 0x00, 0x00, 0x00], # Direct stop Right (0x01)
    "MOTOR_STOP_H":    [0x27, 0x00, 0x05, 0x44, 0x02, 0x00, 0x00, 0x00], # Direct stop Head (0x02)
    
    # High-Level R-Series Control (Command 0x0F), used for scripted/automated movement
    "R2_ROTATE_QUICK": [0x27, 0x42, 0x0F, 0x44, 0x44, 0x03], # Append XX (Dir: 0x00/0xFF), YY (Delay)
    "R2_ROTATE_FULL":  [0x2B, 0x42, 0x0F, 0x48, 0x44, 0x02], # Append XX, YY (Spd), AA(Ramp x2), BB(Delay x2)
    "R2_CENTER_HEAD":  [0x27, 0x42, 0x0F, 0x44, 0x44, 0x01], # Append XX (Spd), YY (Mode: 0x00/0x01)
    "R2_DRIVE":        [0x2B, 0x42, 0x0F, 0x48, 0x44, 0x05], # Append XX (Dir), YY (Spd), AA(Ramp x2), BB(Delay x2)

    # --- BB-SERIES ---
    # BB Rotate Head: Direction (0x00=right, 0xFF=left), Speed, Ramp(x2), Delay(x2).
    "BB_ROTATE_HEAD":  [0x2B, 0x42, 0x0F, 0x48, 0x44, 0x04], # Append XX, YY, AA, AA, BB, BB
    # BB Drive: Heading (0x00-0xFF mixed vector: 0x00=Front, 0x40=Right, 0x80=Back, 0xC0=Left).
    "BB_DRIVE":        [0x2B, 0x42, 0x0F, 0x48, 0x44, 0x05], # Append Heading, Spd, Ramp(x2), Delay(x2)
    "BB_STOP":         [0x2B, 0x42, 0x0F, 0x48, 0x44, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
}

# DROID AUDIO GROUPS
# - Named for the park locations where the audio is typically heard naturally
# - Audio clips are stacked sequentially within these groups
# - Clips range from 1-7
AUDIO_GROUPS = {
    1: "Marketplace",
    2: "Droid Depot",
    3: "Resistance",
    4: "Unknown",
    5: "Droid Detector",
    6: "Dok-Ondar's",
    7: "First Order",
    8: "Activation",
    9: "Motor / Internal",
    10: "Empty",
    11: "Accessory: Blaster",
    12: "Accessory: Thruster"
}

# UI STRINGS
# - These will eventually be loaded from language json files
# - Easy translation
UI_STRINGS = {
    "LIST_ITEM": "[{idx}] {label} MAC: {mac}",
    "UNKNOWN": "Unknown Droid",
    "INVALID": "Invalid Selection",
    
    "MAIN_HEADER": " --- DROID TOOLBOX ---",
    "MAIN_FOOTER": "Choose an option",
    "MAIN_SCAN": "Scan for droids",
    "MAIN_BEACON": "Emit a beacon",
    "MAIN_CONNECT": "Connect to a droid",
    
    "SCAN_HEADER": "--- DROID SCANNER ---",
    "SCAN_FOOTER": "Found droids.",
    "SCAN_MSG": "Scanning for Droids...",
    "SCAN_NONE": "No Droids found",
    "SCAN_PROMPT": "Select a Droid",
    
    "FAVORITES_HEADER": "--- KNOWN DROIDS ---",
    "FAVORITES_EMPTY": "No droids saved yet",
    "FAVORITES_PROMPT": "Select a Favorite",
    "FAVORITES_DELCONF": "Removed from Favorites",
    "FAVORITES_SAVED": "Added to Favorites",
    
    "BEACON_HEADER_MAIN": "--- DROID BEACON CONTROL ---",
    "BEACON_HEADER_LOCATIONS": "--- LOCATION BEACONS ---",
    "BEACON_HEADER_DROIDS": "--- {faction} DROIDS ---",
    "BEACON_FOOTER": "Active: {status}",
    
    "CONN_CONNECTING": "Connecting to {name}...",
    "CONN_FAILED": "Failed to connect",
    "CONN_LOST": "Connection lost. Returning to menu...",
    "CONN_DISCONNECTED": "Disconnected...",
    
    "CONNECTED_HEADER": "--- CONNECTED TO: {name} ---",
    "CONNECTED_PLAY_AUDIO": "Play Audio",
    "CONNECTED_RUN_SCRIPT": "Run Script",
    "CONNECTED_REMOTE_CONTROL": "Remote Control",
    "CONNECTED_DISCONNECT": "Disconnect",
    "CONNECTED_FOOTER": "Choose an option",
    
    "AUDIO_HEADER": "--- AUDIO CONTROL ---",
    "AUDIO_FOOTER1": "Select an audio group",
    "AUDIO_FOOTER2": "Select an audio clip",
    
    "SCRIPTS_HEADER": "--- SCRIPT CONTROL ---",
    "SCRIPTS_FOOTER": "Select a script number (1 - 18)",
    
    "REMOTE_HEADER": "--- REMOTE CONTROL ---",
    "REMOTE_FOOTER": "Remote controls not implemented",
}

# BUTTON CONFIGURATIONS
# See input.py for hardcoded color->button maps
UI_BUTTONS = {
    "SELECT": {"label": "Select",   "btn": "A",  "color_ref": "a"},
    "BACK":   {"label": "Back",     "btn": "B",  "color_ref": "b"},
    "STOP":   {"label": "Stop",     "btn": "X",  "color_ref": "x"},
    "DELETE": {"label": "Delete",   "btn": "X",  "color_ref": "x"},
    "FAV":    {"label": "Favorite", "btn": "Y",  "color_ref": "y"},
    "EXIT":   {"label": "Exit",     "btn": "B",  "color_ref": "b"},
    "CONN":   {"label": "Connect",  "btn": "A",  "color_ref": "a"},
    "SCAN":   {"label": "Scan",     "btn": "X",  "color_ref": "x"},
}