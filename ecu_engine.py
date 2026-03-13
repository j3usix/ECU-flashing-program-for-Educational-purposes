import copy
import sys
import datetime

from processor_profiles import PROCESSOR_PROFILES
from scenarios import SCENARIOS


class SimulatedECU:
    def __init__(self, name: str, version: str, firmware: bytes, profile: dict):
        self.name = name
        self.version = version
        self._firmware = firmware
        self._backup = None
        self.programming_mode = False
        self.profile = profile

    # --- Endianness ---
    def _apply_endianness(self, data: bytes) -> bytes:
        if self.profile["endianness"] == "big":
            return data[::-1]
        return data

    # --- Security Access ---
    def request_security_access(self, seed: int):
        sec = self.profile["security"]
        if sec["type"] == "none":
            return True
        if sec["type"] == "seed_key" and sec["algorithm"] == "xor8":
            return seed ^ 0xA5
        if sec["type"] == "challenge_response":
            return (seed * 17) % 256

    # --- Versioning ---
    def _increment_version(self, version: str) -> str:
        major, minor, patch = map(int, version.split("."))

        if self.profile["versioning"] == "patch":
            patch += 1
        elif self.profile["versioning"] == "minor":
            minor += 1
            patch = 0

        return f"{major}.{minor}.{patch}"

    # --- High-level operations ---
    def identify(self):
        return {
            "ecu_name": self.name,
            "software_version": self.version,
            "firmware_size": len(self._firmware),
        }

    def enter_programming_mode(self):
        self.programming_mode = True
        return True

    def exit_programming_mode(self):
        self.programming_mode = False
        return True

    def read_firmware(self):
        return copy.deepcopy(self._firmware)

    def backup_firmware(self):
        self._backup = copy.deepcopy(self._firmware)
        return True

    def has_backup(self):
        return self._backup is not None

    def restore_backup(self):
        if self._backup is None:
            return False
        self._firmware = copy.deepcopy(self._backup)
        return True

    # --- Flashing ---
    def flash_firmware(self, new_firmware: bytes):
        if not self.programming_mode:
            raise RuntimeError("ECU is not in programming mode.")

        self._erase_for_flash()
        self._firmware = self._apply_endianness(new_firmware)
        self.version = self._increment_version(self.version)
        return True

    # --- Sector erase simulation ---
    def _erase_for_flash(self):
        sector = self.profile["sector_size"]
        erased = bytes([0xFF]) * ((len(self._firmware) // sector) * sector)
        self._firmware = erased
        return True

    # --- Verification ---
    def verify_firmware(self, expected: bytes):
        return self._firmware == expected


class ECUTrainerApp:
    def __init__(self, ecu: SimulatedECU):
        self.ecu = ecu
        self.last_flashed_image = None
        self.log = []

        # Scenario state
        self.active_scenario = None
        self.scenario_initial_block = None
        self.scenario_target_block = None

    # --- Logging ---
    def _log(self, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log.append(f"[{timestamp}] {message}")

    def _do_show_log(self):
        print("\n[SESSION LOG]")
        if not self.log:
            print("  No actions logged yet.\n")
            return
        for entry in self.log:
            print(" ", entry)
        print()

    # --- Memory Map ---
    def _do_memory_map(self):
        print("\n[MEMORY MAP]")

        mem_map = self.ecu.profile["memory_map"]
        total_size = sum(size for _, size in mem_map.values())

        for region, (start, size) in mem_map.items():
            bar_length = int((size / total_size) * 40)
            bar = "#" * bar_length
            print(f"{region.upper():<10} | {bar:<40} | Start: {hex(start)}  Size: {size} bytes")

        print()

    # --- Calibration Editor ---
    def _do_edit_calibration(self):
        blocks = self.ecu.profile.get("calibration_blocks", {})
        print("\n[CALIBRATION BLOCKS]")

        if not blocks:
            print("  This processor profile has no calibration blocks defined.\n")
            return

        for name, (addr, size) in blocks.items():
            print(f"  {name:<15} Start: {hex(addr)}  Size: {size} bytes")

        block_name = input("\nSelect block to edit: ").strip()
        if block_name not in blocks:
            print("  Invalid block.\n")
            return

        addr, size = blocks[block_name]
        fw = bytearray(self.ecu._firmware)
        block = fw[addr:addr+size]

        print("\nRAW HEX:")
        print(" ".join(f"{b:02X}" for b in block))

        try:
            index = int(input("Select byte index to modify: "))
            if index < 0 or index >= size:
                print("  Index out of range.\n")
                return

            new_val = int(input("Enter new value (0–255): "))
            if new_val < 0 or new_val > 255:
                print("  Value out of range.\n")
                return

        except ValueError:
            print("  Invalid input.\n")
            return

        block[index] = new_val
        fw[addr:addr+size] = block
        self.ecu._firmware = bytes(fw)

        print("  Calibration updated.\n")
        self._log(f"Edited calibration block '{block_name}', index {index}, new value {new_val}")

    # --- Scenario Loader ---
    def _do_load_scenario(self):
        print("\n[AVAILABLE SCENARIOS]")
        for key, sc in SCENARIOS.items():
            print(f"  {key:<15} - {sc['name']}")

        scenario_key = input("\nSelect scenario: ").strip()
        if scenario_key not in SCENARIOS:
            print("  Invalid scenario.\n")
            return

        sc = SCENARIOS[scenario_key]
        self.active_scenario = sc

        print(f"\n[SCENARIO LOADED] {sc['name']}")
        print(f"Processor: {sc['processor']}")
        print(f"Description: {sc['description']}")
        print(f"Calibration Block: {sc['calibration_block']}\n")

        profile = PROCESSOR_PROFILES[sc["processor"]]

        # New ECU for scenario
        initial_fw = bytearray(65536)  # 64KB training firmware
        self.ecu = SimulatedECU(
            name="ScenarioECU",
            version="1.0.0",
            firmware=bytes(initial_fw),
            profile=profile
        )

        block_name = sc["calibration_block"]
        addr, size = profile["calibration_blocks"][block_name]

        if "initial_values" in sc:
            values = sc["initial_values"]
            fw = bytearray(self.ecu._firmware)
            for i, v in enumerate(values):
                if i < size:
                    fw[addr + i] = v
            self.ecu._firmware = bytes(fw)

        if "target_values" in sc:
            self.scenario_initial_block = sc["initial_values"]
            self.scenario_target_block = sc["target_values"]

        self._log(f"Loaded scenario '{sc['name']}'")
        print("Scenario ready.\n")

    # --- Scenario Evaluation ---
    def _evaluate_scenario(self):
        if not self.active_scenario or not self.scenario_target_block:
            print("\nNo active scenario with target values.\n")
            return

        sc = self.active_scenario
        block_name = sc["calibration_block"]
        addr, size = self.ecu.profile["calibration_blocks"][block_name]

        fw = self.ecu._firmware
        edited = list(fw[addr:addr + len(self.scenario_target_block)])

        print("\n[SCENARIO EVALUATION]")
        print(f"Scenario: {sc['name']}")

        if edited == self.scenario_target_block:
            print("RESULT: PASS — Calibration changes match expected values.\n")
            self._log(f"Scenario '{sc['name']}' passed")
        else:
            print("RESULT: FAIL — Calibration does not match expected values.\n")
            print("Expected:", self.scenario_target_block)
            print("Got:     ", edited, "\n")
            self._log(f"Scenario '{sc['name']}' failed")

    # --- Hex Viewer ---
    def _do_hex_viewer(self):
        fw = self.ecu._firmware
        print("\n[HEX VIEWER] Showing first 512 bytes...\n")

        for addr in range(0, min(len(fw), 512), 16):
            chunk = fw[addr:addr+16]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            print(f"{addr:04X}:  {hex_str}")

        print("\n(Truncated for readability)\n")

    # --- Calibration Block Viewer ---
    def _do_view_calibration_block(self):
        blocks = self.ecu.profile.get("calibration_blocks", {})
        print("\n[CALIBRATION BLOCKS]")

        if not blocks:
            print("  No calibration blocks defined.\n")
            return

        for name, (addr, size) in blocks.items():
            print(f"  {name:<15} Start: {hex(addr)}  Size: {size} bytes")

        block_name = input("\nSelect block to view: ").strip()
        if block_name not in blocks:
            print("  Invalid block.\n")
            return

        addr, size = blocks[block_name]
        fw = self.ecu._firmware
        block = fw[addr:addr+size]

        print(f"\n[VIEWING BLOCK: {block_name}]")
        print(f"Address: {hex(addr)}  Size: {size} bytes\n")

        for i in range(0, size, 16):
            chunk = block[i:i+16]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            print(f"{addr+i:04X}:  {hex_str}")

        print()

    # --- 2D Table Visualizer ---
    def _do_view_2d_table(self):
        blocks = self.ecu.profile.get("calibration_blocks", {})
        print("\n[2D TABLE BLOCKS]")

        for name, (addr, size) in blocks.items():
            if size in (64, 128, 256):
                print(f"  {name:<15} Start: {hex(addr)}  Size: {size} bytes")

        block_name = input("\nSelect table block: ").strip()
        if block_name not in blocks:
            print("  Invalid block.\n")
            return

        addr, size = blocks[block_name]
        fw = self.ecu._firmware
        block = fw[addr:addr+size]

        if size == 256:
            rows, cols = 16, 16
        elif size == 128:
            rows, cols = 8, 16
        elif size == 64:
            rows, cols = 8, 8
        else:
            print("  Block size not recognized as a 2D table.\n")
            return

        print(f"\n[2D TABLE: {block_name}]  ({rows}x{cols})\n")

        idx = 0
        for _ in range(rows):
            row_vals = block[idx:idx+cols]
            idx += cols
            print(" ".join(f"{v:3d}" for v in row_vals))

        print()

    # --- Curve Visualizer ---
    def _do_view_curve(self):
        blocks = self.ecu.profile.get("calibration_blocks", {})
        print("\n[CURVE BLOCKS]")

        for name, (addr, size) in blocks.items():
            if size <= 64:
                print(f"  {name:<15} Start: {hex(addr)}  Size: {size} bytes")

        block_name = input("\nSelect curve block: ").strip()
        if block_name not in blocks:
            print("  Invalid block.\n")
            return

        addr, size = blocks[block_name]
        fw = self.ecu._firmware
        block = fw[addr:addr+size]

        print(f"\n[CURVE: {block_name}] (size {size})\n")

        if not block:
            print("  Empty block.\n")
            return

        max_val = max(block) or 1

        for i, v in enumerate(block):
            bar = "#" * int((v / max_val) * 40)
            print(f"{i:02d}: {bar} ({v})")

        print()

    # --- Main Loop ---
    def run(self):
        while True:
            self._print_menu()
            choice = input("Select an option: ").strip()

            if choice == "1":
                self._do_identify()
                self._log("Identified ECU")

            elif choice == "2":
                self._do_backup()
                self._log("Backup created")

            elif choice == "3":
                self._do_enter_programming()
                self._log("Entered programming mode")

            elif choice == "4":
                new_data_str = self._do_flash()
                if new_data_str:
                    self._log(f"Flashed firmware: {new_data_str}")

            elif choice == "5":
                result = self._do_verify()
                if result:
                    self._log("Verification successful")
                else:
                    self._log("Verification failed")

            elif choice == "6":
                self._do_restore()
                self._log("Backup restored")

            elif choice == "7":
                self._do_memory_map()

            elif choice == "8":
                self._do_show_log()

            elif choice == "9":
                self._do_edit_calibration()

            elif choice == "10":
                self._do_load_scenario()

            elif choice == "11":
                self._evaluate_scenario()

            elif choice == "12":
                self._do_hex_viewer()

            elif choice == "13":
                self._do_view_calibration_block()

            elif choice == "14":
                self._do_view_2d_table()

            elif choice == "15":
                self._do_view_curve()

            elif choice.lower() in ("q", "quit", "exit"):
                print("Exiting ECU Trainer.")
                sys.exit(0)

            else:
                print("Invalid choice. Please try again.\n")

    # --- Menu ---
    def _print_menu(self):
        print("\n=== ECU TRAINER (SIMULATION MODE) ===")
        print("1) Identify ECU")
        print("2) Backup firmware")
        print("3) Enter programming mode")
        print("4) Flash new firmware (simulated)")
        print("5) Verify last flashed image")
        print("6) Restore backup")
        print("7) View memory map")
        print("8) View session log")
        print("9) Edit calibration block")
        print("10) Load training scenario")
        print("11) Evaluate scenario")
        print("12) View hex dump")
        print("13) View calibration block")
        print("14) View 2D spark/fuel table")
        print("15) View 1D curve")
        print("Q) Quit")
        print("-------------------------------------")

    # --- Actions ---
    def _do_identify(self):
        info = self.ecu.identify()
        print("\n[IDENTIFY]")
        for k, v in info.items():
            print(f"  {k}: {v}")
        print()

    def _do_backup(self):
        print("\n[BACKUP]")
        if self.ecu.backup_firmware():
            print("  Backup created successfully.")
        else:
            print("  Backup failed.")
        print()

    def _do_enter_programming(self):
        print("\n[PROGRAMMING MODE]")
        if self.ecu.enter_programming_mode():
            print("  ECU is now in programming mode.")
        else:
            print("  Failed to enter programming mode.")
        print()

    def _do_flash(self):
        print("\n[FLASH]")
        if not self.ecu.programming_mode:
            print("  ERROR: ECU is not in programming mode.\n")
            return None

        if not self.ecu.has_backup():
            print("  WARNING: No backup exists. Please create a backup first.\n")
            return None

        new_data_str = input("  Enter a short string to represent new firmware: ")
        new_firmware = new_data_str.encode("utf-8")

        self.last_flashed_image = new_firmware
        try:
            self.ecu.flash_firmware(new_firmware)
            print("  Flash operation completed (simulated).")
            print(f"  New software version: {self.ecu.version}")
            print()
            return new_data_str
        except RuntimeError as e:
            print(f"  ERROR: {e}")
            print()
            return None

    def _do_verify(self):
        print("\n[VERIFY]")
        if self.last_flashed_image is None:
            print("  No flashed image to verify.\n")
            return False

        ok = self.ecu.verify_firmware(self.last_flashed_image)
        if ok:
            print("  Verification successful.")
        else:
            print("  Verification FAILED.")
        print()
        return ok

    def _do_restore(self):
        print("\n[RESTORE]")
        if not self.ecu.has_backup():
            print("  No backup available.\n")
            return

        if self.ecu.restore_backup():
            print("  Backup restored successfully.")
        else:
            print("  Restore failed.")
        print()


def main():
    profile_name = input("Select processor profile (RISC-V-OpenECU / TriCore-Lite / Renesas-Sim): ")
    profile = PROCESSOR_PROFILES.get(profile_name, PROCESSOR_PROFILES["RISC-V-OpenECU"])

    initial_firmware = b"ECU_FIRMWARE_V1"
    ecu = SimulatedECU(
        name="TrainingECU-01",
        version="1.0.0",
        firmware=initial_firmware,
        profile=profile
    )

    app = ECUTrainerApp(ecu)
    app.run()


if __name__ == "__main__":
    main()