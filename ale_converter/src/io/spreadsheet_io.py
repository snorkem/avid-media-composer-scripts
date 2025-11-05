"""
Spreadsheet I/O operations for CSV and Excel files.

This module handles reading from and writing to CSV and Excel formats,
including conversion to/from ALE format.
"""

from pathlib import Path
from typing import Optional, Tuple
import pandas as pd

from ..models.ale_data import ALEData, ALEHeader


class SpreadsheetReader:
    """
    Reads spreadsheet files (CSV and Excel).

    This class provides methods to read database files in various formats
    and parse them into DataFrames.
    """

    @staticmethod
    def read_file(
        file_path: Path,
        sheet_name: Optional[str] = None,
        verbose: bool = False
    ) -> pd.DataFrame:
        """
        Read a spreadsheet file (CSV or Excel).

        Args:
            file_path: Path to the spreadsheet file
            sheet_name: Optional sheet name for Excel files
            verbose: Enable verbose logging

        Returns:
            DataFrame containing the spreadsheet data

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is not supported
        """
        if verbose:
            print(f"Reading spreadsheet from {file_path}")

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        file_ext = file_path.suffix.lower()

        try:
            if file_ext in ['.xlsx', '.xls', '.xlsm']:
                df = SpreadsheetReader._read_excel(file_path, sheet_name, verbose)
            elif file_ext == '.csv':
                df = pd.read_csv(file_path, dtype=str)
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")

            if verbose:
                print(f"Successfully read {len(df)} rows from {file_path}")

            return df

        except Exception as e:
            raise ValueError(f"Error reading file: {e}")

    @staticmethod
    def _read_excel(
        file_path: Path,
        sheet_name: Optional[str] = None,
        verbose: bool = False
    ) -> pd.DataFrame:
        """
        Read an Excel file with optional sheet selection.

        Args:
            file_path: Path to Excel file
            sheet_name: Optional sheet name or index
            verbose: Enable verbose logging

        Returns:
            DataFrame with the Excel data
        """
        try:
            import openpyxl
        except ImportError:
            raise ImportError("Excel support requires openpyxl. Install with: pip install openpyxl")

        # Get available sheets
        xl = pd.ExcelFile(file_path)
        sheet_names = xl.sheet_names

        # Determine which sheet to read
        if sheet_name is not None:
            # Try to use the specified sheet
            if sheet_name in sheet_names:
                target_sheet = sheet_name
            else:
                # Try as an index
                try:
                    index = int(sheet_name)
                    if 0 <= index < len(sheet_names):
                        target_sheet = sheet_names[index]
                    else:
                        raise ValueError(f"Sheet index {index} out of range")
                except ValueError:
                    raise ValueError(f"Sheet '{sheet_name}' not found. Available: {sheet_names}")
        else:
            # Use first sheet
            target_sheet = sheet_names[0]
            if verbose and len(sheet_names) > 1:
                print(f"Found {len(sheet_names)} sheets. Using first: '{target_sheet}'")

        return pd.read_excel(file_path, sheet_name=target_sheet, dtype=str)

    @staticmethod
    def list_excel_sheets(file_path: Path) -> list:
        """
        List all sheets in an Excel file.

        Args:
            file_path: Path to Excel file

        Returns:
            List of sheet names
        """
        try:
            import openpyxl
            wb = openpyxl.load_workbook(file_path, read_only=True)
            sheet_names = wb.sheetnames
            wb.close()
            return sheet_names
        except ImportError:
            raise ImportError("Excel support requires openpyxl")


class SpreadsheetWriter:
    """
    Writes spreadsheet files (CSV and Excel).

    This class provides methods to export ALE data to spreadsheet formats.
    """

    @staticmethod
    def write_ale_to_spreadsheet(
        ale_data: ALEData,
        output_path: Path,
        format: str = 'csv',
        verbose: bool = False
    ) -> str:
        """
        Export ALE data to CSV or Excel format.

        Args:
            ale_data: ALEData instance to export
            output_path: Path for the output file
            format: Output format ('csv' or 'excel')
            verbose: Enable verbose logging

        Returns:
            Path to the created file

        Raises:
            ValueError: If format is not supported
        """
        if verbose:
            print(f"Exporting ALE to {format.upper()} format")

        # Create header dataframe
        df_header = pd.DataFrame([
            {"Header_Key": "FIELD_DELIM", "Header_Value": ale_data.header.field_delim},
            {"Header_Key": "VIDEO_FORMAT", "Header_Value": ale_data.header.video_format},
            {"Header_Key": "AUDIO_FORMAT", "Header_Value": ale_data.header.audio_format},
            {"Header_Key": "FPS", "Header_Value": str(ale_data.header.fps)}
        ])

        # Add custom fields
        for key, value in ale_data.header.custom_fields.items():
            df_header = pd.concat([
                df_header,
                pd.DataFrame([{"Header_Key": key, "Header_Value": value}])
            ])

        # Get main data
        df_ale = ale_data.data.copy()
        df_ale.fillna('', inplace=True)

        if format.lower() == 'csv':
            # For CSV, create two separate files
            main_output_path = output_path
            header_output_path = output_path.with_stem(f"{output_path.stem}_headers")

            df_ale.to_csv(main_output_path, index=False)
            df_header.to_csv(header_output_path.with_suffix('.csv'), index=False)

            if verbose:
                print(f"Exported main data to: {main_output_path}")
                print(f"Exported header data to: {header_output_path.with_suffix('.csv')}")

            return str(main_output_path)

        elif format.lower() == 'excel':
            try:
                import openpyxl

                with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                    df_ale.to_excel(writer, sheet_name='ALE_Data', index=False)
                    df_header.to_excel(writer, sheet_name='ALE_Headers', index=False)

                if verbose:
                    print(f"Exported both data and headers to Excel: {output_path}")

                return str(output_path)

            except ImportError:
                if verbose:
                    print("Excel export requires openpyxl. Falling back to CSV")

                # Fallback to CSV
                return SpreadsheetWriter.write_ale_to_spreadsheet(
                    ale_data, output_path.with_suffix('.csv'), 'csv', verbose
                )
        else:
            raise ValueError(f"Unsupported format: {format}")

    @staticmethod
    def convert_spreadsheet_to_ale(
        spreadsheet_path: Path,
        output_path: Path,
        fps: float,
        template_ale_path: Optional[Path] = None,
        verbose: bool = False
    ) -> str:
        """
        Convert a CSV or Excel file to ALE format.

        Args:
            spreadsheet_path: Path to the spreadsheet file
            output_path: Path for the output ALE file
            fps: Frames per second setting
            template_ale_path: Optional template ALE for header structure
            verbose: Enable verbose logging

        Returns:
            Path to the created ALE file

        Raises:
            ValueError: If conversion fails
        """
        if verbose:
            print(f"Converting spreadsheet to ALE format with FPS: {fps}")

        # Read the spreadsheet
        reader = SpreadsheetReader()
        df = reader.read_file(spreadsheet_path, verbose=verbose)

        # Fill NaN values
        df.fillna('', inplace=True)

        # Add null row (required for ALE format)
        null_row = pd.DataFrame([["null"] * len(df.columns)], columns=df.columns)
        df = pd.concat([df, null_row], ignore_index=True)

        # Get or create header
        if template_ale_path and template_ale_path.exists():
            from .ale_reader import ALEReader
            template_ale = ALEReader.read_file(template_ale_path)
            header = template_ale.header
            header.fps = fps  # Override FPS
        else:
            header = ALEHeader(fps=fps)

        # Create ALEData instance
        ale_data = ALEData(header=header, data=df)

        # Write using ALEWriter
        from .ale_writer import ALEWriter
        return ALEWriter.write_file(ale_data, output_path, verbose=verbose)
