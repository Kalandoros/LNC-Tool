from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

import src.utils.nc_handler as nc_handler
import src.utils.path_handler as path_handler

pd.options.display.float_format = '{:12.3e}'.format
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.precision', 3)
pd.set_option('display.width', 1000)


@dataclass()
class NcInputPath:
    file_path: str
    nc_path: str

@dataclass()
class NcOutputPath:
    level_1: Optional[str] = None               # unterwerksbezeichnung
    level_2: Optional[str] = None               # anlagenklasse
    level_3: Optional[str] = None               # disziplin
    level_4: Optional[str] = None               # dokumentenart
    level_5: Optional[str] = None               # dokumentnummer
    level_6: Optional[str|list[str]] = None     # freitext
    level_7: Optional[int|float] = None         # revision
    level_8: Optional[int|float] = None         # projektnummer

@dataclass()
class NcFilter:
    level_1: Optional[list[str]] = None         # unterwerksbezeichnung
    level_2: Optional[list[str]] = None         # anlagenklasse
    level_3: Optional[list[str]] = None         # disziplin
    level_4: Optional[list[str]] = None         # dokumentenart
    level_5: Optional[list[str]] = None         # dokumentnummer
    level_6: Optional[list[str]] = None         # freitext
    level_7: Optional[list[str]] = None         # revision
    level_8: Optional[list[str]] = None         # projektnummer

@dataclass()
class NcGetterPath:
    input: NcInputPath
    result: NcOutputPath = field(default_factory=NcOutputPath)
    filter: NcFilter = field(default_factory=NcFilter)
    convention = "nc_eng_unterwerke"
    _nc_data: Optional[pd.DataFrame] = field(default=None, init=False, repr=False)

    def file_name_with_extension(self) -> NcOutputPath:
        self.result.level_6 = path_handler.get_file_name_with_extension(self.input.file_path).replace("_", "-")
        return self.result

    def file_name_without_extension(self) -> NcOutputPath:
        self.result.level_6 = path_handler.get_file_name_without_extension(self.input.file_path).replace("_", "-")
        return self.result

    def path_seperated_list(self) -> NcOutputPath:
        self.result.level_6 = path_handler.get_path_directories(self.input.file_path)
        return self.result

    def nc_unterwerk(self) -> NcOutputPath:
        self.result.level_1 = nc_handler.load_nc_csv_as_pandas(self.input.nc_path).iat[0, 0]      # row, column
        return self.result

    def nc_anlagenteil(self) -> NcOutputPath:
        self.result.level_2 = nc_handler.load_nc_csv_as_pandas(self.input.nc_path).iat[0, 1]      # row, column
        return self.result

    def nc_disziplin(self) -> NcOutputPath:
        self.result.level_3 = nc_handler.load_nc_csv_as_pandas(self.input.nc_path).iat[0, 2]      # row, column
        return self.result

    def nc_dokumentart_filter(self) -> NcFilter:
        if self.result.level_3 is None:
            self.nc_disziplin()
        disziplin_mask = nc_handler.load_nc_csv_as_pandas(self.input.nc_path).iloc[:, 2].eq(self.result.level_3)
        dokumentarten = nc_handler.load_nc_csv_as_pandas(self.input.nc_path).loc[disziplin_mask, nc_handler.load_nc_csv_as_pandas(self.input.nc_path).columns[4]]
        dokumentarten = [str(value) for value in dokumentarten if str(value).strip()]
        self.filter.level_3 = dokumentarten
        return self.filter

    def nc_dokumentart(self) -> NcOutputPath:
        if self.filter.level_3 is None:
            self.nc_dokumentart_filter()
        #disziplin_mask = pd.Series(self.filter.level_3, index=self._get_nc_data().index)
        self.result.level_4 = self.nc_dokumentart_filter().level_3[3] if self.nc_dokumentart_filter() else None
        return self.result

    def nc_dokumentennummer(self) -> NcOutputPath:
        self.result.level_5 = nc_handler.load_nc_csv_as_pandas(self.input.nc_path).iat[0, 6]      # row, column
        return self.result

def main() -> None:
    # Test of path and name based components
    test_nc_input_path = NcInputPath(file_path="C:/User/angel/Downloads/Field Ageing Behaiviour of Long Rods Analysed According Cigre TB 306, 2025 - Ruokanen, Vrabec.pdf", nc_path="C:/Users/angel/OneDrive/Documents/GitHub/LNC-Tool/src/data/nc_eng_unterwerke.csv")
    test_nc_getter_path = NcGetterPath(input=test_nc_input_path)
    print(test_nc_getter_path.file_name_with_extension())
    print(test_nc_getter_path.file_name_without_extension())
    print(test_nc_getter_path.path_seperated_list())
    print(test_nc_getter_path.result)

    # Test of nc based components
    print(test_nc_getter_path.nc_unterwerk())
    print(test_nc_getter_path.nc_anlagenteil())
    print(test_nc_getter_path.nc_disziplin())
    print(test_nc_getter_path.nc_dokumentart_filter())
    print(test_nc_getter_path.filter.level_3)
    print(test_nc_getter_path.nc_dokumentart())
    print(test_nc_getter_path.nc_dokumentennummer())

if __name__ == "__main__":
    main()
