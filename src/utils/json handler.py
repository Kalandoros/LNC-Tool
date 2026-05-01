import pathlib
import json

path = "src/data/nc_nested.json"

def get_json_file(path):
    with open(path, 'r') as f:
        return json.load(f)

def main():
    json_file = get_json_file(path)
    print(json_file)

if __name__ == '__main__':
    main()