import json
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "nc_nested.json"

def get_json_file(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)

def main():
    json_file = get_json_file(DATA_FILE)
    print(json_file)

if __name__ == '__main__':
    main()
