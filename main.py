from pathlib import Path
import socket
import subprocess
import re
import uuid

import pandas as pd
from taipy.gui import Gui, notify
from taipy.gui.builder import Page, button, html, input, part, selector, table, text


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
TABLE_DROPDOWN_COLUMNS = ["Level_1", "Level_2", "Level_3", "Level_4", "Level_5"]
ROW_NUMBER_COLUMN = "Nr"
ROW_NUMBER_WIDTH_PX = 40
LEVEL_COLUMN_WIDTHS_PX = {
    "Level_1": 220,
    "Level_2": 190,
    "Level_3": 190,
    "Level_4": 220,
    "Level_5": 210,
    "Level_6": 180,
    "Level_7": 130,
    "Level_8": 180,
}
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1F]')
LEVEL_SUBLABELS = {
    "Level_1": "Unterwerksbezeichnung",
    "Level_2": "Anlagenklasse",
    "Level_3": "Disziplin",
    "Level_4": "Dokumentenart",
    "Level_5": "Dokumentnummer",
    "Level_6": "Freitext",
    "Level_7": "Revision",
    "Level_8": "Projektnummer",
}


def _build_table_columns() -> dict[str, dict[str, object]]:
    columns: dict[str, dict[str, object]] = {
        ROW_NUMBER_COLUMN: {"index": 0, "title": "Nr\nZeile", "width": f"{ROW_NUMBER_WIDTH_PX}px"}
    }
    for idx, column in enumerate(LEVEL_COLUMNS, start=1):
        sublabel = LEVEL_SUBLABELS.get(column, "")
        title = f"{column}\n{sublabel}" if sublabel else column
        columns[column] = {"index": idx, "title": title}
        width_px = LEVEL_COLUMN_WIDTHS_PX.get(column)
        width = f"{width_px}px" if width_px is not None else None
        if width:
            columns[column]["width"] = width
    return columns


TABLE_COLUMNS = _build_table_columns()


def _load_csv_with_fallback(csv_path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return pd.read_csv(
                csv_path,
                sep=";",
                dtype=str,
                keep_default_na=False,
                encoding=encoding,
            )
        except UnicodeDecodeError:
            continue
    return pd.read_csv(csv_path, sep=";", dtype=str, keep_default_na=False, encoding="latin-1")


def _unique_non_empty(values: pd.Series) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in values:
        value = str(raw).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _load_level_lovs() -> dict[str, list[str]]:
    csv_path = Path(__file__).parent / "src" / "data" / "nc_eng_unterwerke.csv"
    if not csv_path.exists():
        return {column: [] for column in TABLE_DROPDOWN_COLUMNS}

    try:
        csv_df = _load_csv_with_fallback(csv_path)
    except Exception:
        return {column: [] for column in TABLE_DROPDOWN_COLUMNS}

    column_index_map = {
        "Level_1": 0,  # Unterwerksbezeichnung
        "Level_2": 1,  # Anlagenklasse
        "Level_3": 2,  # Disziplin
        "Level_4": 4,  # Dokumentart
        "Level_5": 6,  # Dokumentnummer
    }

    lovs: dict[str, list[str]] = {}
    for level_column, csv_col_idx in column_index_map.items():
        if csv_col_idx >= len(csv_df.columns):
            lovs[level_column] = []
            continue
        lovs[level_column] = _unique_non_empty(csv_df.iloc[:, csv_col_idx])
    return lovs


LEVEL_LOVS = _load_level_lovs()

selected_folder = ""
selected_files: list[str] = []
status_text = "Bitte zuerst einen Ordner auswaehlen."
selection_text = "Ausgewaehlte Zeilen: keine (Bulk wirkt auf alle Zeilen)."
nc_rows = pd.DataFrame(columns=[ROW_NUMBER_COLUMN, *LEVEL_COLUMNS])
selected_table_rows: list[int] = []
range_start = ""
range_end = ""

level_1_lov = LEVEL_LOVS.get("Level_1", [])
level_2_lov = LEVEL_LOVS.get("Level_2", [])
level_3_lov = LEVEL_LOVS.get("Level_3", [])
level_4_lov = LEVEL_LOVS.get("Level_4", [])
level_5_lov = LEVEL_LOVS.get("Level_5", [])

bulk_level_1 = ""
bulk_level_2 = ""
bulk_level_3 = ""
bulk_level_4 = ""
bulk_level_5 = ""
bulk_level_6 = ""
bulk_level_7 = ""
bulk_level_8 = ""


def _empty_rows(row_count: int) -> pd.DataFrame:
    rows = pd.DataFrame(
        [{column: "" for column in LEVEL_COLUMNS} for _ in range(row_count)],
        columns=LEVEL_COLUMNS,
    )
    rows.insert(0, ROW_NUMBER_COLUMN, list(range(1, row_count + 1)))
    return rows


def _update_selection_text(state) -> None:
    selected_count = len(state.selected_table_rows or [])
    if selected_count:
        state.selection_text = f"Ausgewaehlte Zeilen: {selected_count} Zeile(n)."
    else:
        state.selection_text = "Ausgewaehlte Zeilen: keine (Bulk wirkt auf alle Zeilen)."


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
    state.selected_table_rows = []
    state.range_start = ""
    state.range_end = ""
    _update_selection_text(state)
    state.status_text = f"Ordner: {folder} | Dateien: {len(files)}"

    if files:
        _apply_nc_vorschlag_to_rows(state)
        notify(state, "success", f"{len(files)} Dateien geladen. NC-Vorschlag automatisch angewendet.")
    else:
        notify(state, "warning", "Der gewaehlte Ordner enthaelt keine Dateien.")


def _apply_nc_vorschlag_to_rows(state) -> bool:
    if state.nc_rows.empty:
        return False

    suggested = state.nc_rows.copy()
    for row_index, file_path in enumerate(state.selected_files):
        file_obj = Path(file_path)
        suggested.at[row_index, "Level_6"] = file_obj.stem
        if not str(suggested.at[row_index, "Level_7"]).strip():
            suggested.at[row_index, "Level_7"] = "0"

    state.nc_rows = suggested
    return True


def on_nc_vorschlag(state, _id=None, _payload=None) -> None:
    if not _apply_nc_vorschlag_to_rows(state):
        notify(state, "warning", "Keine Dateien geladen.")
        return
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


def on_table_action(state, _var_name, payload) -> None:
    row_index = payload.get("index")
    if row_index is None:
        return

    try:
        index = int(row_index)
    except (TypeError, ValueError):
        return

    selected = list(state.selected_table_rows or [])
    if index in selected:
        selected.remove(index)
    else:
        selected.append(index)

    selected.sort()
    state.selected_table_rows = selected
    clicked_row_number = str(index + 1)
    state.range_start = clicked_row_number
    state.range_end = clicked_row_number
    _update_selection_text(state)


def on_clear_selection(state, _id=None, _payload=None) -> None:
    state.selected_table_rows = []
    state.range_start = ""
    state.range_end = ""
    _update_selection_text(state)


def _parse_row_number(value: object) -> int | None:
    text_value = str(value).strip() if value is not None else ""
    if not text_value or not text_value.isdigit():
        return None
    parsed = int(text_value)
    if parsed < 1:
        return None
    return parsed


def _apply_range_selection(state) -> None:
    start_nr = _parse_row_number(state.range_start)
    end_nr = _parse_row_number(state.range_end)
    if start_nr is None and end_nr is None:
        return
    if start_nr is None:
        start_nr = end_nr
    if end_nr is None:
        end_nr = start_nr
    if start_nr is None or end_nr is None:
        return

    min_nr, max_nr = sorted((start_nr, end_nr))
    max_allowed = len(state.nc_rows)
    if max_allowed <= 0:
        return
    if min_nr > max_allowed or max_nr > max_allowed:
        return

    start_idx = min_nr - 1
    end_idx = max_nr - 1
    state.selected_table_rows = list(range(start_idx, end_idx + 1))
    state.range_start = str(min_nr)
    state.range_end = str(max_nr)
    _update_selection_text(state)


def on_range_input_change(state, var_name, value) -> None:
    _ = value
    if var_name not in ("range_start", "range_end"):
        return
    _apply_range_selection(state)


def _apply_single_bulk_change(state, var_name: str, value: object) -> None:
    if state.nc_rows.empty:
        return

    prefix = "bulk_level_"
    if not isinstance(var_name, str) or not var_name.startswith(prefix):
        return

    level_suffix = var_name[len(prefix) :]
    if not level_suffix.isdigit():
        return

    level_index = int(level_suffix)
    if level_index < 1 or level_index > len(LEVEL_COLUMNS):
        return
    if level_index == 7:  # Level_7 bulk is intentionally disabled
        return

    new_value = str(value).strip() if value is not None else ""
    if not new_value:
        return

    target_column = LEVEL_COLUMNS[level_index - 1]
    updated_rows = state.nc_rows.copy()
    selected = sorted(
        {
            int(idx)
            for idx in (state.selected_table_rows or [])
            if str(idx).strip().isdigit() and 0 <= int(idx) < len(updated_rows)
        }
    )
    target_indices = selected if selected else list(range(len(updated_rows)))

    for row_idx in target_indices:
        updated_rows.at[row_idx, target_column] = new_value

    state.nc_rows = updated_rows

def on_bulk_field_change(state, var_name, value) -> None:
    _apply_single_bulk_change(state, var_name, value)


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

.selection-tools {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 10px;
}

.selection-tools-label,
.selection-tools-sep {
  white-space: nowrap;
}

.selection-clear-btn {
  min-width: 150px;
}

.bulk-panel {
  border: 1px solid #d8d8d8;
  border-radius: 6px;
  padding: 10px 0;
  margin-bottom: 10px;
  background: #fafafa;
  overflow-x: auto;
}

.bulk-grid {
  display: grid;
  grid-template-columns: 220px 190px 190px 220px 210px 180px 130px 180px;
  min-width: 1600px;
  row-gap: 8px;
  column-gap: 0;
  padding-left: 80px;
  box-sizing: border-box;
  align-items: end;
}

.bulk-col {
  padding-right: 10px;
  box-sizing: border-box;
}

.bulk-col-last {
  padding-right: 0;
}

.bulk-item-label {
  display: block;
  font-size: 12px;
  margin-bottom: 4px;
}

.table-wrap {
  height: calc(100vh - 260px);
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

.nc-table thead .MuiTableSortLabel-root {
  white-space: pre-line;
  line-height: 1.15;
  align-items: flex-start;
}

.nc-table td .MuiInput-root .MuiInput-input {
  width: 80px !important;
}

.nc-table .MuiTableBody-root .MuiTableRow-root.Mui-selected .MuiTableCell-root {
  background-color: rgba(25, 118, 210, 0.32) !important;
}

.nc-table .MuiTableBody-root .MuiTableRow-root.Mui-selected:hover .MuiTableCell-root {
  background-color: rgba(25, 118, 210, 0.4) !important;
}

.nc-table .MuiTableBody-root .MuiTableRow-root.Mui-selected .MuiTableCell-root:first-child {
  box-shadow: inset 3px 0 0 #1976d2;
}
"""


with Page() as page:
    html("style", CSS)
    with part(class_name="app-shell"):
        text("{status_text}", class_name="status-line")
        with part(class_name="bulk-panel"):
            with part(class_name="bulk-grid"):
                with part(class_name="bulk-col"):
                    text("Level_1", class_name="bulk-item-label")
                    selector(
                        value="{bulk_level_1}",
                        lov="{level_1_lov}",
                        dropdown=True,
                        width="100%",
                        on_change=on_bulk_field_change,
                    )
                with part(class_name="bulk-col"):
                    text("Level_2", class_name="bulk-item-label")
                    selector(
                        value="{bulk_level_2}",
                        lov="{level_2_lov}",
                        dropdown=True,
                        width="100%",
                        on_change=on_bulk_field_change,
                    )
                with part(class_name="bulk-col"):
                    text("Level_3", class_name="bulk-item-label")
                    selector(
                        value="{bulk_level_3}",
                        lov="{level_3_lov}",
                        dropdown=True,
                        width="100%",
                        on_change=on_bulk_field_change,
                    )
                with part(class_name="bulk-col"):
                    text("Level_4", class_name="bulk-item-label")
                    selector(
                        value="{bulk_level_4}",
                        lov="{level_4_lov}",
                        dropdown=True,
                        width="100%",
                        on_change=on_bulk_field_change,
                    )
                with part(class_name="bulk-col"):
                    text("Level_5", class_name="bulk-item-label")
                    selector(
                        value="{bulk_level_5}",
                        lov="{level_5_lov}",
                        dropdown=True,
                        width="100%",
                        on_change=on_bulk_field_change,
                    )
                with part(class_name="bulk-col"):
                    text("Level_6", class_name="bulk-item-label")
                    input(value="{bulk_level_6}", width="100%", on_change=on_bulk_field_change)
                with part(class_name="bulk-col"):
                    text("Level_7", class_name="bulk-item-label")
                    input(value="{bulk_level_7}", width="100%", active=False)
                with part(class_name="bulk-col bulk-col-last"):
                    text("Level_8", class_name="bulk-item-label")
                    input(value="{bulk_level_8}", width="100%", on_change=on_bulk_field_change)
        text("{selection_text}", class_name="status-line")
        with part(class_name="selection-tools"):
            text("Zeile(n)-Nr.:", class_name="selection-tools-label")
            input(value="{range_start}", width="80px", on_change=on_range_input_change)
            text("-", class_name="selection-tools-sep")
            input(value="{range_end}", width="80px", on_change=on_range_input_change)
            button("Auswahl zuruecksetzen", on_action=on_clear_selection, class_name="selection-clear-btn")
        with part(class_name="table-wrap"):
            table(
                data="{nc_rows}",
                columns=TABLE_COLUMNS,
                class_name="nc-table",
                editable=True,
                editable__Nr=False,
                lov__Level_1="{level_1_lov}",
                lov__Level_2="{level_2_lov}",
                lov__Level_3="{level_3_lov}",
                lov__Level_4="{level_4_lov}",
                lov__Level_5="{level_5_lov}",
                selected="{selected_table_rows}",
                on_action=on_table_action,
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
    Gui(page=page).run(
        title="LNC Tool",
        use_reloader=False,
        dark_mode=False,
        port=port,
    )
