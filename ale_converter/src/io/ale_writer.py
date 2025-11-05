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

        # Convert data to tab-separated format
        csv_content = ale_data.data.to_csv(sep='\t', index=False)

        # Extract column names and data rows
        csv_header, csv_data = csv_content.split('\n', 1)

        # Format the column section
        column_section = "Column\n" + csv_header

        # Clean up formatting issues in data
        csv_data = ALEWriter._clean_data_formatting(csv_data)

        # Assemble the complete ALE file
        ale_content = header_section + "\n\n" + column_section + "\n\nData\n" + csv_data

        return ale_content

    @staticmethod
    def _clean_data_formatting(data: str) -> str:
        """
        Clean up formatting issues in the data section.

        Args:
            data: Raw data section string

        Returns:
            Cleaned data section string
        """
        # Remove problematic quote patterns
        data = data.replace('\"\"\"', '')  # Remove triple double quotes
        data = data.replace('\"\"', '\"')  # Remove double double quotes
        data = data.replace('\t\"', '\t')  # Remove leading double quotes
        data = data.replace('\"\t', '\t')  # Remove trailing double quotes

        return data

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
