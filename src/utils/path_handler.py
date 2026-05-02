import pathlib

def get_file_path() -> pathlib.Path:
    """
    Retrieves the file path for the current module.

    Returns:
        pathlib.Path: The file path of the current module.
    """
    return pathlib.Path(__file__)

def get_path_directories(file_path: str | pathlib.Path | None = None) -> list[str]:
    """
    Retrieves the directories of the file path as list of strings.

    Returns:
        list: List of directories in the file path.
    """
    file_path = get_file_path() if file_path is None else file_path
    return list(pathlib.Path(file_path).parts[:-1])

def get_file_name_with_extension(file_path: str | pathlib.Path | None = None) -> str:
    """
    Retrieves the file name with extension from the file path.
    If no path is provided, it uses this module's path.

    Returns:
        str: The file name with extension.
    """
    target = pathlib.Path(file_path) if file_path is not None else get_file_path()
    return target.name

def get_file_name_without_extension(file_path: str | pathlib.Path | None = None) -> str:
    """
    Retrieves the file name without extension from the given path.
    If no path is provided, it uses this module's path.

    Returns:
        str: The file name without extension.
    """
    target = pathlib.Path(file_path) if file_path is not None else get_file_path()
    return target.stem

def main() -> None:
    """
    Main function to demonstrate the usage of functions in this module.
    """
    file_path = get_file_path()
    print(f"File path: {file_path}")

    directories = get_path_directories()
    print(f"Directories: {directories}")

    file_name_with_extension = get_file_name_with_extension()
    print(f"File name: {file_name_with_extension}")

    file_name_without_extension = get_file_name_without_extension()
    print(f"File name: {file_name_without_extension}")

if __name__ == "__main__":
    main()
