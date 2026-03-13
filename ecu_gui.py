import customtkinter as ctk
from ecu_engine import ECUTrainerApp, SimulatedECU
from processor_profiles import PROCESSOR_PROFILES
from scenarios import SCENARIOS

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class TableEditorWindow(ctk.CTkToplevel):
    def __init__(self, master, engine: ECUTrainerApp):
        super().__init__(master)
        self.title("2D Table Editor")
        self.geometry("900x600")
        self.engine = engine
        self.block_name = None
        self.entries = []
        self.rows = 0
        self.cols = 0

        self._build_ui()

    def _build_ui(self):
        top = ctk.CTkFrame(self, corner_radius=16)
        top.pack(fill="x", padx=16, pady=16)

        ctk.CTkLabel(top, text="Select 2D Table Block", font=("SF Pro Display", 18, "bold")).pack(side="left", padx=8)

        blocks = self.engine.ecu.profile.get("calibration_blocks", {})
        self.table_blocks = {
            name: (addr, size)
            for name, (addr, size) in blocks.items()
            if blocks and blocks[name][1] in (64, 128, 256)
        }

        self.block_var = ctk.StringVar(value=list(self.table_blocks.keys())[0] if self.table_blocks else "")
        self.block_menu = ctk.CTkOptionMenu(
            top,
            variable=self.block_var,
            values=list(self.table_blocks.keys()),
            command=lambda _: self._load_block()
        )
        self.block_menu.pack(side="left", padx=8)

        self.save_btn = ctk.CTkButton(top, text="Save Table", command=self._save_block)
        self.save_btn.pack(side="right", padx=8)

        self.table_frame = ctk.CTkScrollableFrame(self, corner_radius=16)
        self.table_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        if self.table_blocks:
            self._load_block()

    def _load_block(self):
        for w in self.table_frame.winfo_children():
            w.destroy()
        self.entries.clear()

        self.block_name = self.block_var.get()
        addr, size = self.table_blocks[self.block_name]
        fw = self.engine.ecu._firmware
        block = fw[addr:addr + size]

        if size == 256:
            self.rows, self.cols = 16, 16
        elif size == 128:
            self.rows, self.cols = 8, 16
        elif size == 64:
            self.rows, self.cols = 8, 8
        else:
            return

        self.entries = [[None for _ in range(self.cols)] for _ in range(self.rows)]

        idx = 0
        for r in range(self.rows):
            for c in range(self.cols):
                val = block[idx]
                idx += 1
                e = ctk.CTkEntry(self.table_frame, width=40)
                e.grid(row=r, column=c, padx=2, pady=2)
                e.insert(0, str(val))
                self.entries[r][c] = e

    def _save_block(self):
        if not self.block_name:
            return

        addr, size = self.table_blocks[self.block_name]
        fw = bytearray(self.engine.ecu._firmware)

        idx = 0
        for r in range(self.rows):
            for c in range(self.cols):
                text = self.entries[r][c].get().strip()
                try:
                    v = int(text)
                except ValueError:
                    v = 0
                v = max(0, min(255, v))
                fw[addr + idx] = v
                idx += 1

        self.engine.ecu._firmware = bytes(fw)
        self.engine._log(f"2D table '{self.block_name}' edited via GUI")
        self.destroy()


class ECUTrainerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("ECU Trainer — Modern GUI")
        self.geometry("1280x800")
        self.minsize(1100, 700)

        profile = PROCESSOR_PROFILES["RISC-V-OpenECU"]
        ecu = SimulatedECU("TrainingECU-01", "1.0.0", b"ECU_FIRMWARE_V1", profile)
        self.engine = ECUTrainerApp(ecu)

        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=20)
        self.sidebar.pack(side="left", fill="y", padx=16, pady=16)

        self.content = ctk.CTkFrame(self, corner_radius=24)
        self.content.pack(side="right", fill="both", expand=True, padx=16, pady=16)

        self._build_sidebar()
        self._show_dashboard(animated=False)

    def _build_sidebar(self):
        title = ctk.CTkLabel(self.sidebar, text="ECU Trainer", font=("SF Pro Display", 24, "bold"))
        title.pack(pady=(24, 8))

        subtitle = ctk.CTkLabel(self.sidebar, text="Simulation Suite", font=("SF Pro Display", 14))
        subtitle.pack(pady=(0, 24))

        buttons = [
            ("🏠  Dashboard", self._show_dashboard),
            ("⚡  Flashing", self._show_flashing),
            ("🧩  Calibration", self._show_calibration),
            ("📊  Visualizers", self._show_visualizers),
            ("🎓  Scenarios", self._show_scenarios),
            ("📜  Logs", self._show_logs),
        ]

        for label, command in buttons:
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                corner_radius=14,
                height=40,
                command=lambda c=command: c()
            )
            btn.pack(fill="x", padx=16, pady=4)

        toggle_label = ctk.CTkLabel(self.sidebar, text="Appearance", font=("SF Pro Display", 14, "bold"))
        toggle_label.pack(pady=(24, 4))

        self.appearance_option = ctk.CTkOptionMenu(self.sidebar, values=["light", "dark"], command=self._change_appearance)
        self.appearance_option.set("light")
        self.appearance_option.pack(fill="x", padx=16, pady=(0, 16))

    def _change_appearance(self, mode):
        ctk.set_appearance_mode(mode)

   