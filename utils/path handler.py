import pathlib

def get_file_path() -> pathlib.Path:
    """
    Retrieves the file path for the current module.

    Returns:
        pathlib.Path: The file path of the current module.
    """
    return pathlib.Path(__file__)

def get_path_directories() -> list[str]:
    """
    Retrieves the directories of the file path as list of strings.

    Returns:
        list: List of directories in the file path.
    """
    file_path = get_file_path()
    return list(file_path.parts[:-1])

def main() -> None:
    """
    Main function to demonstrate the usage of get_file_path.
    """
    file_path = get_file_path()
    print(f"File path: {file_path}")

    directories = get_path_directories()
    print(f"Directories: {directories}")

if __name__ == "__main__":
    main()
