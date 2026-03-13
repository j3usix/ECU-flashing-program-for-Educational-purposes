PROCESSOR_PROFILES = {

    # ---------------------------------------------------------
    # RISC‑V OpenECU — simple, clean, beginner‑friendly profile
    # ---------------------------------------------------------
    "RISC-V-OpenECU": {
        "endianness": "little",
        "sector_size": 256,

        # Memory layout: (start_address, size)
        "memory_map": {
            "boot": (0x0000, 4096),
            "app":  (0x1000, 16384),
            "cal":  (0x5000, 4096),
        },

        # No security for beginners
        "security": {
            "type": "none"
        },

        # Version increments patch number only
        "versioning": "patch",

        # Calibration blocks for editing
        "calibration_blocks": {
            "fuel_trim":   (0x5000, 64),
            "spark_table": (0x5040, 256),
            "idle_target": (0x5140, 8)
        }
    },  # ← missing comma added here


    # ---------------------------------------------------------
    # TriCore‑Lite — big‑endian, larger sectors, XOR seed/key
    # ---------------------------------------------------------
    "TriCore-Lite": {
        "endianness": "big",
        "sector_size": 512,

        "memory_map": {
            "boot": (0x0000, 8192),
            "app":  (0x2000, 32768),
            "cal":  (0xA000, 8192),
        },

        "security": {
            "type": "seed_key",
            "algorithm": "xor8"   # seed ^ 0xA5
        },

        "versioning": "patch",

        "calibration_blocks": {
            "fuel_trim":   (0xA000, 64),
            "spark_table": (0xA040, 256),
            "idle_target": (0xA140, 8)
        }
    },  # ← missing comma added here


    # ---------------------------------------------------------
    # Renesas‑Sim — little‑endian, small sectors, hash challenge
    # ---------------------------------------------------------
    "Renesas-Sim": {
        "endianness": "little",
        "sector_size": 128,

        "memory_map": {
            "boot": (0x0000, 2048),
            "app":  (0x0800, 8192),
            "cal":  (0x2800, 2048),
        },

        "security": {
            "type": "challenge_response",
            "algorithm": "simple_hash"  # (seed * 17) % 256
        },

        # Minor version increments for this
        "versioning": "minor",

        "calibration_blocks": {
            "fuel_trim":   (0x2800, 64),
            "spark_table": (0x2840, 256),
            "idle_target": (0x2940, 8)
        }
    }
}

def resolve_profile(name: str):
    return PROCESSOR_PROFILES.get(name)