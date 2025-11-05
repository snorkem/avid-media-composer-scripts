"""
ALE file reading functionality.

This module handles reading and parsing AVID ALE files.
"""

from pathlib import Path
from typing import Optional
import pandas as pd
import re

from ..models.ale_data import ALEData, ALEHeader


class ALEReader:
    """
    Reads and parses AVID ALE files.

    This class provides methods to read ALE files and extract both header
    metadata and clip data into structured formats.
    """

    @staticmethod
    def read_file(ale_path: Path, verbose: bool = False) -> ALEData:
        """
        Read an ALE file and parse its contents.

        Args:
            ale_path: Path to the ALE file
            verbose: Enable verbose logging

        Returns:
            ALEData instance containing header and clip data

        Raises:
            FileNotFoundError: If the ALE file doesn't exist
            ValueError: If the ALE file format is invalid
        """
        if verbose:
            print(f"Reading ALE file from {ale_path}")

        if not ale_path.exists():
            raise FileNotFoundError(f"ALE file not found: {ale_path}")

        # Read the entire file
        with open(ale_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse header section
        header = ALEReader._parse_header(content)

        # Parse data section
        data = ALEReader._parse_data(ale_path)

        if verbose:
            print(f"Successfully read ALE with {len(data)} clips")

        return ALEData(header=header, data=data)

    @staticmethod
    def _parse_header(content: str) -> ALEHeader:
        """
        Parse the header section from ALE file content.

        Args:
            content: Full ALE file content as string

        Returns:
            ALEHeader instance with parsed metadata
        """
        # Handle case where heading items are all on one line
        if "HeadingFIELD_DELIM" in content:
            # Parse the header line by adding newlines where needed
            header_line = content.split("Column")[0].strip()

            # Extract the FPS value
            fps_match = re.search(r'FPS\s+(\d+\.\d+)', header_line)
            fps = float(fps_match.group(1)) if fps_match else 23.976

            # Create properly formatted header
            header_section = (
                "Heading\n"
                "FIELD_DELIM\tTABS\n"
                "VIDEO_FORMAT\t1080\n"
                "AUDIO_FORMAT\t48khz\n"
                f"FPS\t{fps}"
            )
        else:
            # Find the start of Column section
            column_start_index = content.find("\nColumn")
            if column_start_index == -1:
                column_start_index = content.find("\nData")

            if column_start_index == -1:
                # Use default header if can't find sections
                header_section = (
                    "Heading\n"
                    "FIELD_DELIM\tTABS\n"
                    "VIDEO_FORMAT\t1080\n"
                    "AUDIO_FORMAT\t48khz\n"
                    "FPS\t23.976"
                )
            else:
                # Extract the header (everything before Column section)
                header_section = content[:column_start_index].strip()

        return ALEHeader.from_string(header_section)

    @staticmethod
    def _parse_data(ale_path: Path) -> pd.DataFrame:
        """
        Parse the data section from an ALE file.

        Args:
            ale_path: Path to the ALE file

        Returns:
            DataFrame containing the clip data
        """
        # Read the entire file to find section markers
        with open(ale_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Find the Column and Data section markers
        column_line_idx = None
        data_line_idx = None

        for i, line in enumerate(lines):
            if line.strip() == "Column" or line.strip().startswith("Column"):
                column_line_idx = i
            elif line.strip() == "Data" or line.strip().startswith("Data"):
                data_line_idx = i
                break

        if column_line_idx is None or data_line_idx is None:
            raise ValueError("Could not find Column or Data sections in ALE file")

        # The column headers should be on the line after "Column"
        header_line_idx = column_line_idx + 1

        # Extract column names
        column_line = lines[header_line_idx].strip()
        columns = [col.strip() for col in column_line.split('\t')]

        # Parse data rows (everything after "Data" line)
        data_rows = []
        for line in lines[data_line_idx + 1:]:
            line = line.strip()
            if line and line != 'null':
                # Split by tab and clean up
                values = line.split('\t')
                # Ensure we have the right number of columns
                while len(values) < len(columns):
                    values.append('')
                values = values[:len(columns)]
                data_rows.append(values)

        # Create DataFrame
        ale = pd.DataFrame(data_rows, columns=columns)

        # Clean up the data
        ale = ale[ale.columns.drop(list(ale.filter(regex='Unnamed')))]
        ale.fillna('', inplace=True)
        ale = ale.replace('\n', '', regex=True)

        return ale

    @staticmethod
    def get_column_headers(ale_path: Path) -> list:
        """
        Extract just the column headers from an ALE file.

        Args:
            ale_path: Path to the ALE file

        Returns:
            List of column names
        """
        # Read the entire file to find section markers
        with open(ale_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Find the Column section marker
        for i, line in enumerate(lines):
            if line.strip() == "Column" or line.strip().startswith("Column"):
                # The column headers should be on the next line
                if i + 1 < len(lines):
                    column_line = lines[i + 1].strip()
                    columns = [col.strip() for col in column_line.split('\t')]
                    return columns

        raise ValueError("Could not find Column section in ALE file")
