"""
ALE file writing functionality.

This module handles writing ALE files with proper formatting.
"""

from pathlib import Path
from typing import Optional
import pandas as pd

from ..models.ale_data import ALEData


class ALEWriter:
    """
    Writes ALE files in the proper format.

    This class handles the serialization of ALEData objects to properly
    formatted ALE files that can be read by AVID systems.
    """

    @staticmethod
    def write_file(ale_data: ALEData, output_path: Path, verbose: bool = False) -> str:
        """
        Write ALEData to a file in ALE format.

        Args:
            ale_data: ALEData instance to write
            output_path: Path where the ALE file should be written
            verbose: Enable verbose logging

        Returns:
            Path to the created file as string

        Raises:
            IOError: If file cannot be written
        """
        if verbose:
            print(f"Writing ALE file to {output_path}")

        # Generate the ALE content
        content = ALEWriter._generate_content(ale_data)

        # Write to file
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)

            if verbose:
                print(f"Successfully wrote {len(ale_data.data)} clips to {output_path}")

            return str(output_path)

        except Exception as e:
            raise IOError(f"Error writing ALE file: {e}")

    @staticmethod
    def _generate_content(ale_data: ALEData) -> str:
        """
        Generate the complete ALE file content.

        Args:
            ale_data: ALEData instance to serialize

        Returns:
            Complete ALE file content as string
        """
        # Get header section
        header_section = ale_data.header.to_string()

        # ALE is plain tab-delimited text with no quoting, so write fields
        # verbatim instead of going through CSV quoting and undoing it.
        df = ale_data.data.fillna('')
        column_line = '\t'.join(ALEWriter._format_field(col) for col in df.columns)
        data_lines = [
            '\t'.join(ALEWriter._format_field(value) for value in row)
            for row in df.itertuples(index=False, name=None)
        ]

        # Format the column section
        column_section = "Column\n" + column_line

        data_section = ''.join(line + '\n' for line in data_lines)

        # Assemble the complete ALE file
        ale_content = header_section + "\n\n" + column_section + "\n\nData\n" + data_section

        return ale_content

    @staticmethod
    def _format_field(value) -> str:
        """
        Convert a value to a single ALE field.

        Tabs and line breaks would split the field or the row, so they are
        replaced with spaces. All other characters, quotes included, are kept.

        Args:
            value: Cell value

        Returns:
            Field text safe for a tab-delimited ALE row
        """
        text = str(value)
        return text.replace('\t', ' ').replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')

    @staticmethod
    def preview_content(ale_data: ALEData, num_lines: int = 20) -> str:
        """
        Generate a preview of the ALE content.

        Args:
            ale_data: ALEData instance to preview
            num_lines: Number of lines to include in preview

        Returns:
            Preview string with first num_lines of the ALE file
        """
        content = ALEWriter._generate_content(ale_data)
        lines = content.split('\n')[:num_lines]
        return '\n'.join(lines)
