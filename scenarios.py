SCENARIOS = {
    "lean_idle": {
        "name": "Lean Idle Condition",
        "processor": "RISC-V-OpenECU",
        "description": "Idle AFR too lean. Increase idle fuel trim by +8%.",
        "calibration_block": "fuel_trim",
        "expected_change": "+8%",
        "initial_values": [20, 20, 20, 20, 20, 20, 20, 20],
        "target_values":  [22, 22, 22, 22, 22, 22, 22, 22]
    },

    "knock_load": {
        "name": "Ignition Knock Under Load",
        "processor": "TriCore-Lite",
        "description": "Knock detected at mid-range RPM. Reduce timing by 3–5 degrees.",
        "calibration_block": "spark_table",
        "expected_change": "-3 to -5 degrees",
        "initial_values": [30] * 16,   # 16-cell spark table
        "target_values":  [26] * 16    # reduced timing
    }
}
