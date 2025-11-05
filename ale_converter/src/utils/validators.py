"""
Input validation utilities.

This module provides validation functions for user inputs including
file paths, FPS values, and other parameters.
"""

from pathlib import Path
from typing import List, Tuple


class FileValidator:
    """
    Validates file paths and file-related inputs.

    This class provides static methods for validating various file-related
    inputs to ensure they meet requirements before processing.
    """

    @staticmethod
    def validate_input_file(file_path: Path, extensions: List[str] = None) -> Tuple[bool, str]:
        """
        Validate that an input file exists and has the correct extension.

        Args:
            file_path: Path to validate
            extensions: Optional list of valid extensions (e.g., ['.ale', '.csv'])

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(file_path, Path):
            file_path = Path(file_path)

        # Check if file exists
        if not file_path.exists():
            return False, f"File not found: {file_path}"

        # Check if it's a file (not a directory)
        if not file_path.is_file():
            return False, f"Path is not a file: {file_path}"

        # Check extension if specified
        if extensions:
            if file_path.suffix.lower() not in [ext.lower() for ext in extensions]:
                return False, f"Invalid file extension. Expected one of: {extensions}"

        return True, ""

    @staticmethod
    def validate_output_path(file_path: Path, must_not_exist: bool = False) -> Tuple[bool, str]:
        """
        Validate an output file path.

        Args:
            file_path: Path to validate
            must_not_exist: If True, file must not already exist

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(file_path, Path):
            file_path = Path(file_path)

        # Check if parent directory exists
        if not file_path.parent.exists():
            return False, f"Parent directory does not exist: {file_path.parent}"

        # Check if parent is writable
        if not file_path.parent.is_dir():
            return False, f"Parent path is not a directory: {file_path.parent}"

        # Check if file already exists (if required)
        if must_not_exist and file_path.exists():
            return False, f"File already exists: {file_path}"

        return True, ""

    @staticmethod
    def validate_ale_file(file_path: Path) -> Tuple[bool, str]:
        """
        Validate that a file is a valid ALE file.

        Args:
            file_path: Path to the ALE file

        Returns:
            Tuple of (is_valid, error_message)
        """
        # First check basic file validity
        is_valid, error = FileValidator.validate_input_file(file_path, ['.ale'])
        if not is_valid:
            return is_valid, error

        # Check file content for ALE markers
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(500)  # Read first 500 chars

            # Look for ALE structure markers
            if 'Heading' not in content and 'Column' not in content:
                return False, "File does not appear to be a valid ALE file"

            return True, ""

        except Exception as e:
            return False, f"Error reading file: {e}"

    @staticmethod
    def validate_spreadsheet_file(file_path: Path) -> Tuple[bool, str]:
        """
        Validate that a file is a valid spreadsheet (CSV or Excel).

        Args:
            file_path: Path to the spreadsheet file

        Returns:
            Tuple of (is_valid, error_message)
        """
        valid_extensions = ['.csv', '.xlsx', '.xls', '.xlsm']
        return FileValidator.validate_input_file(file_path, valid_extensions)


class FPSValidator:
    """
    Validates FPS (frames per second) values.

    This class provides validation for FPS values to ensure they are
    compatible with AVID systems.
    """

    # Standard FPS values supported by AVID
    VALID_FPS_VALUES = [23.976, 29.97, 59.94, 24, 25, 30, 60, 119.88, 120]

    @staticmethod
    def validate_fps(fps: float, strict: bool = True) -> Tuple[bool, str]:
        """
        Validate an FPS value.

        Args:
            fps: FPS value to validate
            strict: If True, only allow standard values. If False, allow any positive number

        Returns:
            Tuple of (is_valid, error_message/warning_message)
        """
        # Check if it's a positive number
        try:
            fps_float = float(fps)
        except (TypeError, ValueError):
            return False, "FPS must be a number"

        if fps_float <= 0:
            return False, "FPS must be a positive number"

        # Check against standard values
        if strict:
            if fps_float not in FPSValidator.VALID_FPS_VALUES:
                return False, (
                    f"FPS {fps_float} is not a standard value. "
                    f"Valid values: {FPSValidator.VALID_FPS_VALUES}"
                )
        else:
            # Non-strict mode: warn but allow
            if fps_float not in FPSValidator.VALID_FPS_VALUES:
                return True, (
                    f"Warning: FPS {fps_float} is not a standard value. "
                    f"This may cause compatibility issues. "
                    f"Recommended values: {FPSValidator.VALID_FPS_VALUES}"
                )

        return True, ""

    @staticmethod
    def get_closest_standard_fps(fps: float) -> float:
        """
        Get the closest standard FPS value to the given value.

        Args:
            fps: FPS value to match

        Returns:
            Closest standard FPS value
        """
        return min(FPSValidator.VALID_FPS_VALUES, key=lambda x: abs(x - fps))

    @staticmethod
    def list_valid_fps() -> List[float]:
        """
        Get list of all valid FPS values.

        Returns:
            List of standard FPS values
        """
        return FPSValidator.VALID_FPS_VALUES.copy()
