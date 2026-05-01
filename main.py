from pathlib import Path
import socket
import tkinter as tk
from tkinter import filedialog

import pandas as pd
from taipy.gui import Gui, notify


LEVEL_COLUMNS = [
    "Level_1",
    "Level_2",
    "Level_3",
    "Level_4",
    "Level_5",
    "Level_6",
    "Level_7",
    "Level_8",
]

selected_folder = ""
selected_files: list[str] = []
status_text = "Bitte zuerst einen Ordner auswaehlen."
nc_rows = pd.DataFrame(columns=LEVEL_COLUMNS)


def _choose_folder() -> str:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    folder = filedialog.askdirectory(title="Ordner auswaehlen")
    root.destroy()
    return folder


def on_select_folder(state) -> None:
    folder = _choose_folder()
    if not folder:
        return

    files = [str(p) for p in sorted(Path(folder).iterdir()) if p.is_file()]
    rows = [{column: "" for column in LEVEL_COLUMNS} for _ in files]

    state.selected_folder = folder
    state.selected_files = files
    state.nc_rows = pd.DataFrame(rows, columns=LEVEL_COLUMNS)
    state.status_text = f"Ordner: {folder} | Dateien: {len(files)}"
    notify(state, "success", f"{len(files)} Dateien geladen.")


def on_nc_vorschlag(state) -> None:
    if state.nc_rows.empty:
        notify(state, "warning", "Keine Dateien geladen.")
        return

    suggested = state.nc_rows.copy()
    for row_index, file_path in enumerate(state.selected_files):
        file_obj = Path(file_path)
        suggested.at[row_index, "Level_6"] = file_obj.stem
        if not str(suggested.at[row_index, "Level_7"]).strip():
            suggested.at[row_index, "Level_7"] = "0"

    state.nc_rows = suggested
    notify(state, "success", "NC-Vorschlaege erzeugt.")


def on_nc_uebernehmen(state) -> None:
    if state.nc_rows.empty:
        notify(state, "warning", "Keine Zeilen zum Uebernehmen.")
        return

    state.status_text = f"NC-Uebernehmen ausgefuehrt fuer {len(state.nc_rows)} Zeilen."
    notify(state, "info", f"{len(state.nc_rows)} Zeilen uebernommen.")


page = """
<style>
html, body, #root {
  height: 100%;
}

.main-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 12px 16px 88px 16px;
  box-sizing: border-box;
}

.status-text {
  margin-bottom: 10px;
}

.table-scroll {
  flex: 1 1 auto;
  overflow: auto;
  border: 1px solid #d8d8d8;
  border-radius: 6px;
}

.fixed-footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  gap: 10px;
  justify-content: center;
  align-items: center;
  padding: 12px 16px;
  background: #ffffff;
  border-top: 1px solid #d8d8d8;
  z-index: 1000;
}

.footer-btn {
  min-width: 150px;
}
</style>

<|part|class_name=main-page|
<|{status_text}|text|class_name=status-text|>

<|part|class_name=table-scroll|
<|{nc_rows}|table|editable|rebuild|show_all|>
|>

<|part|class_name=fixed-footer|
<|Ordner auswaehlen|button|on_action=on_select_folder|class_name=footer-btn|>
<|NC-Vorschlag|button|on_action=on_nc_vorschlag|class_name=footer-btn|>
<|NC-Uebernehmen|button|on_action=on_nc_uebernehmen|class_name=footer-btn|>
|>
|>
"""

if __name__ == "__main__":
    port = 5000
    for candidate_port in range(5000, 5101):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", candidate_port)) != 0:
                port = candidate_port
                break
    print(f"LNC Tool startet auf http://127.0.0.1:{port}")
    Gui(page=page).run(title="LNC Tool", use_reloader=False, dark_mode=False, port=port)
