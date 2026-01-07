# Droid signals are extensively documented
# https://docs.google.com/spreadsheets/d/13P_GE6tNYpGvoVUTEQvA3SQzMqpZ-SoiWaTNoJoTV9Q

# LOCATION BEACONS
# - Droids that react to a location beacon will not sleep for 6 hours
# - The first element in each tuple tells the droid which audio group to play from
# - Droids will therefore have different reactions for some areas depending on their faction
# - Third element in each tuple is cooldown timer, multiply by 5 to get cooldown in seconds
# - Droids have a minimum cooldown of 60 seconds between location beacon reactions, 0xFF may be an override
# - Locations mapped: https://galaxysedgetech.epizy.com
LOCATIONS = {
    "1": (0x01, "Ronto Roasters", 0x02), # Also emits near other food vendors in ther marketplace
    "2": (0x02, "Oil Baths", 0x02), # Also called the droid playground; the group of droids behind the depot
    "3": (0x03, "Resistance Base", 0x02),
    "4": (0x04, "Unknown", 0x02), # Droids react to this locarion, but it has not been discovered anywhere yet
    "5": (0x05, "Droid Depot", 0x02), # Also emits in front of the marketplace
    "6": (0x06, "Den of Antiquities", 0x02),
    "7": (0x07, "First Order Base", 0x02),
    "8": (0x05, "Oga's Droid Detector", 0xFF),
    "9": (0x07, "First Order Alert", 0xFF)
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
# - To connect to a droid the rermote must be turned off
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

# Because we are using BTCTL and BlueZ, we need to split the bytes. Sending 0x222001 is not the same as sending 0x22 20 01.
# With each LOGON command sent, a droid should return 2F 32 81 45 4B 10 01 44 44 11 11 01 00 00 00 00 on the NOTIFY characteristic.

# DROID COMMAND PACKET STRUCTURE
# Byte 1: [0x1F + Total Bytes] - Packet length header
# Byte 2: [0x42] if Command ID is 0x0F, else [0x00] - Logic Guard
# Byte 3: [Command ID] - The action type (e.g., 0x0F for actions/sounds)
# Byte 4: [Data Length + 0x40] - Payload length header
# Bytes 5-N: The actual command data/payload (Max 31 bytes)
COMMANDS = {
    "LOGON": "22 20 01"
}
