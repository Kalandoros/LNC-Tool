import pathlib
from typing import Any
import pandas as pd

pd.options.display.float_format = '{:12.3e}'.format
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.precision', 3)
pd.set_option('display.width', 1000)

file_path = pathlib.Path(__file__).resolve().parents[1] / "data" / "nc_eng_unterwerke.csv"

def load_nc_csv_as_pandas(file_path: str | pathlib.Path | None = None) -> pd.DataFrame:
    """
    Loads the convention data from a CSV file.

    Returns:
        pd.DataFrame: The loaded data.
    """
    nc_pandas = pd.read_csv(file_path, header=0, delimiter=";", na_filter=False)
    return nc_pandas

def main() -> None:
    """
    Main function to demonstrate the usage of functions in this module.
    """
    nc_data = load_nc_csv_as_pandas(file_path)
    print(nc_data)

if __name__ == "__main__":
    main()
