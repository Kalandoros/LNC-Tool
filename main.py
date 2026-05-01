from pathlib import Path
import socket
import subprocess
import re
import uuid

import pandas as pd
from taipy.gui import Gui, notify
from taipy.gui.builder import Page, button, html, part, table, text


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
ROW_NUMBER_COLUMN = "Nr"
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1F]')

selected_folder = ""
selected_files: list[str] = []
status_text = "Bitte zuerst einen Ordner auswaehlen."
nc_rows = pd.DataFrame(columns=[ROW_NUMBER_COLUMN, *LEVEL_COLUMNS])


def _empty_rows(row_count: int) -> pd.DataFrame:
    rows = pd.DataFrame(
        [{column: "" for column in LEVEL_COLUMNS} for _ in range(row_count)],
        columns=LEVEL_COLUMNS,
    )
    rows.insert(0, ROW_NUMBER_COLUMN, list(range(1, row_count + 1)))
    return rows


def _choose_folder() -> str:
    # Native Windows folder picker via PowerShell.
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
        "$dialog.Description = 'Ordner auswaehlen'; "
        "$dialog.UseDescriptionForTitle = $true; "
        "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { "
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "Write-Output $dialog.SelectedPath }"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        check=False,
    )

    raw_stdout = result.stdout if result.stdout is not None else b""
    if not raw_stdout:
        return ""

    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw_stdout.decode(encoding).strip()
        except UnicodeDecodeError:
            continue

    return raw_stdout.decode("latin-1", errors="replace").strip()


def _sanitize_filename_part(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    text = INVALID_FILENAME_CHARS.sub("_", text)
    text = text.strip(" .")
    return text


def _build_nc_filename_stem(row: pd.Series) -> str:
    parts: list[str] = []
    for column in LEVEL_COLUMNS:
        part = _sanitize_filename_part(row.get(column))
        if part:
            parts.append(part)
    return "_".join(parts)


def on_select_folder(state, _id=None, _payload=None) -> None:
    folder = _choose_folder()
    if not folder:
        return

    files = [str(path) for path in sorted(Path(folder).iterdir()) if path.is_file()]
    state.selected_folder = folder
    state.selected_files = files
    state.nc_rows = _empty_rows(len(files))
    state.status_text = f"Ordner: {folder} | Dateien: {len(files)}"

    if files:
        notify(state, "success", f"{len(files)} Dateien geladen.")
    else:
        notify(state, "warning", "Der gewaehlte Ordner enthaelt keine Dateien.")


def on_nc_vorschlag(state, _id=None, _payload=None) -> None:
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
    notify(state, "success", "NC-Vorschlag erzeugt.")


def on_nc_uebernehmen(state, _id=None, _payload=None) -> None:
    if state.nc_rows.empty:
        notify(state, "warning", "Keine Zeilen zum Uebernehmen.")
        return

    rows_by_nr: dict[int, pd.Series] = {}
    for _, row in state.nc_rows.iterrows():
        try:
            row_number = int(float(row[ROW_NUMBER_COLUMN]))
        except (KeyError, ValueError, TypeError):
            continue
        rows_by_nr[row_number] = row

    planned_ops: list[dict[str, Path]] = []
    for index, file_path in enumerate(state.selected_files, start=1):
        source_path = Path(file_path)
        if not source_path.exists():
            notify(state, "error", f"Datei nicht gefunden: {source_path}")
            return

        row = rows_by_nr.get(index)
        target_stem = _build_nc_filename_stem(row) if row is not None else ""
        if not target_stem:
            target_stem = source_path.stem

        target_path = source_path.with_name(f"{target_stem}{source_path.suffix}")
        planned_ops.append({"src": source_path, "target": target_path})

    rename_ops = [op for op in planned_ops if op["src"] != op["target"]]
    if not rename_ops:
        notify(state, "info", "Keine Umbenennung noetig.")
        return

    source_set = {str(op["src"]).lower() for op in planned_ops}
    target_owner: dict[str, Path] = {}
    for op in rename_ops:
        target_key = str(op["target"]).lower()
        if target_key in target_owner and target_owner[target_key] != op["src"]:
            notify(state, "error", f"Zielname mehrfach vorhanden: {op['target'].name}")
            return
        target_owner[target_key] = op["src"]

        if op["target"].exists() and target_key not in source_set:
            notify(state, "error", f"Zieldatei existiert bereits: {op['target']}")
            return

    phase1_done: list[dict[str, Path]] = []
    phase2_done: list[dict[str, Path]] = []
    try:
        for op in rename_ops:
            temp_path = op["src"].with_name(f".lnc_tmp_{uuid.uuid4().hex}{op['src'].suffix}")
            while temp_path.exists():
                temp_path = op["src"].with_name(f".lnc_tmp_{uuid.uuid4().hex}{op['src'].suffix}")
            op["src"].rename(temp_path)
            op["temp"] = temp_path
            phase1_done.append(op)

        for op in rename_ops:
            op["temp"].rename(op["target"])
            phase2_done.append(op)

    except Exception as exc:
        for op in reversed(phase2_done):
            if op["target"].exists():
                op["target"].rename(op["src"])
        for op in reversed(phase1_done):
            if op["temp"].exists():
                op["temp"].rename(op["src"])
        notify(state, "error", f"Umbenennung fehlgeschlagen: {exc}")
        return

    state.selected_files = [str(op["target"]) for op in planned_ops]
    state.status_text = f"NC-Uebernehmen ausgefuehrt. Umbenannt: {len(rename_ops)} Dateien."
    notify(state, "success", f"{len(rename_ops)} Dateien umbenannt.")


CSS = """
html, body, #root {
  height: 100%;
  margin: 0;
}

.app-shell {
  height: 100vh;
  box-sizing: border-box;
  padding: 12px 16px 88px 16px;
}

.status-line {
  margin-bottom: 10px;
}

.table-wrap {
  height: calc(100vh - 150px);
  overflow: auto;
  border: 1px solid #d8d8d8;
  border-radius: 6px;
}

.footer-fixed {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  gap: 10px;
  justify-content: center;
  align-items: center;
  padding: 12px 16px;
  box-sizing: border-box;
  background: #ffffff;
  border-top: 1px solid #d8d8d8;
  z-index: 1000;
}

.footer-btn {
  min-width: 170px;
}
"""


with Page() as page:
    html("style", CSS)
    with part(class_name="app-shell"):
        text("{status_text}", class_name="status-line")
        with part(class_name="table-wrap"):
            table(
                data="{nc_rows}",
                editable=True,
                editable__Nr=False,
                on_add=False,
                on_delete=False,
                rebuild=True,
                show_all=True,
                width="100%",
                height="100%",
            )
        with part(class_name="footer-fixed"):
            button("Ordner auswaehlen", on_action=on_select_folder, class_name="footer-btn")
            button("NC-Vorschlag", on_action=on_nc_vorschlag, class_name="footer-btn")
            button("NC-Uebernehmen", on_action=on_nc_uebernehmen, class_name="footer-btn")


def _find_free_port(start: int = 5000, end: int = 5100) -> int:
    for candidate_port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", candidate_port)) != 0:
                return candidate_port
    return start


if __name__ == "__main__":
    port = _find_free_port()
    print(f"LNC Tool startet auf http://127.0.0.1:{port}")
    Gui(page=page).run(title="LNC Tool", use_reloader=False, dark_mode=False, port=port)
