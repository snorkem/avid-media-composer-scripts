"""
ALE Converter V2 - Refactored

This script converts and merges AVID ALE files with metadata from an AIRTABLE CSV export.
It extracts archival IDs from clip names, matches them with database records,
and creates a new ALE file with the merged metadata.

This is a thin wrapper around the modular src/ package.

Usage:
    python ale_converter.py merge --ale AVID.ale --db AIRTABLE.csv [--output OUTPUT.ale]
    python ale_converter.py export --ale AVID.ale [--output OUTPUT.csv] [--format csv]
    python ale_converter.py convert --spreadsheet FILE.csv --fps 23.976 [--output OUTPUT.ale]
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

# Import from the src package
from src.io.ale_reader import ALEReader
from src.io.ale_writer import ALEWriter
from src.io.spreadsheet_io import SpreadsheetReader, SpreadsheetWriter
from src.processing.data_cleaner import DataCleaner
from src.processing.id_extractor import IDExtractor
from src.processing.merger import DataMerger
from src.config.column_mapper import ColumnMapper
from src.utils.validators import FileValidator, FPSValidator


class ALEConverter:
    """
    Main converter class that orchestrates the conversion process.

    This class serves as a facade that coordinates the various modular
    components to perform ALE conversion operations.
    """

    def __init__(
        self,
        ale_path: Optional[Path] = None,
        db_path: Optional[Path] = None,
        output_path: Optional[Path] = None,
        verbose: bool = False
    ):
        """
        Initialize the converter.

        Args:
            ale_path: Path to the ALE file
            db_path: Path to the database file (CSV/Excel)
            output_path: Path for the output file
            verbose: Enable verbose logging
        """
        self.ale_path = Path(ale_path) if ale_path else None
        self.db_path = Path(db_path) if db_path else None
        self.output_path = Path(output_path) if output_path else Path("AVID_WITH_ARC_DATA.ale")
        self.verbose = verbose

    def convert_with_merge(
        self,
        column_mapper: Optional[ColumnMapper] = None,
        id_position: Optional[int] = None
    ) -> str:
        """
        Run the complete merge conversion process.

        Args:
            column_mapper: Optional ColumnMapper for custom column configuration
            id_position: Optional position for manual ID extraction

        Returns:
            Path to the created ALE file

        Raises:
            ValueError: If required files are not set or don't exist
        """
        if not self.ale_path or not self.db_path:
            raise ValueError("Both ale_path and db_path must be set")

        # Validate input files
        is_valid, error = FileValidator.validate_ale_file(self.ale_path)
        if not is_valid:
            raise ValueError(f"Invalid ALE file: {error}")

        is_valid, error = FileValidator.validate_spreadsheet_file(self.db_path)
        if not is_valid:
            raise ValueError(f"Invalid database file: {error}")

        # Read files
        if self.verbose:
            print(f"Starting conversion of {self.ale_path} with {self.db_path}")

        ale_data = ALEReader.read_file(self.ale_path, verbose=self.verbose)
        db_df = SpreadsheetReader.read_file(self.db_path, verbose=self.verbose)

        # Clean data
        db_df = DataCleaner.clean_database(db_df, verbose=self.verbose)
        ale_data.data = DataCleaner.clean_ale_data(ale_data.data, verbose=self.verbose)

        # Extract IDs
        db_df = IDExtractor.extract_database_ids(db_df, verbose=self.verbose)
        ale_data.data = IDExtractor.extract_ale_ids(
            ale_data.data,
            position=id_position,
            verbose=self.verbose
        )

        # Check ID overlap and try alternatives if needed
        stats = IDExtractor.analyze_id_overlap(ale_data.data, db_df, verbose=self.verbose)
        if stats['matching_ids'] == 0:
            if self.verbose:
                print("No matching IDs found. Trying alternative extraction methods...")

            db_ids = set(db_df['ARC_ID'].dropna().unique())
            alternative_result = IDExtractor.try_alternative_extractions(
                ale_data.data, db_ids, verbose=self.verbose
            )

            if alternative_result is not None:
                ale_data.data = alternative_result
                # Re-analyze ID overlap after alternative extraction
                IDExtractor.analyze_id_overlap(ale_data.data, db_df, verbose=self.verbose)

        # Merge data
        merged_df = DataMerger.merge_data(ale_data.data, db_df, verbose=self.verbose)

        # Prepare for output
        columns_to_drop = column_mapper.columns_to_drop if column_mapper else None
        columns_to_rename = column_mapper.columns_to_rename if column_mapper else None

        output_df = DataMerger.prepare_for_ale_output(
            merged_df,
            columns_to_drop=columns_to_drop,
            columns_to_rename=columns_to_rename,
            verbose=self.verbose
        )

        # Update ale_data with merged output
        ale_data.data = output_df

        # Write output
        return ALEWriter.write_file(ale_data, self.output_path, verbose=self.verbose)

    @staticmethod
    def export_ale_to_spreadsheet(
        ale_path: Path,
        output_path: Optional[Path] = None,
        output_format: str = 'csv',
        fps: float = 23.976,
        verbose: bool = False
    ) -> str:
        """
        Export an ALE file to CSV or Excel format.

        Args:
            ale_path: Path to the ALE file
            output_path: Optional output path
            output_format: Output format ('csv' or 'excel')
            fps: FPS value to use in the export
            verbose: Enable verbose logging

        Returns:
            Path to the created file
        """
        # Validate FPS
        is_valid, message = FPSValidator.validate_fps(fps, strict=False)
        if not is_valid:
            raise ValueError(message)
        elif message:  # Warning
            if verbose:
                print(message)

        # Read ALE file
        ale_data = ALEReader.read_file(ale_path, verbose=verbose)

        # Update FPS if different
        ale_data.header.fps = fps

        # Determine output path
        if output_path is None:
            if output_format == 'csv':
                output_path = ale_path.with_suffix('.csv')
            else:
                output_path = ale_path.with_suffix('.xlsx')

        # Write to spreadsheet
        return SpreadsheetWriter.write_ale_to_spreadsheet(
            ale_data, output_path, output_format, verbose=verbose
        )

    @staticmethod
    def convert_spreadsheet_to_ale(
        spreadsheet_path: Path,
        output_path: Optional[Path] = None,
        template_ale_path: Optional[Path] = None,
        fps: float = 23.976,
        verbose: bool = False
    ) -> str:
        """
        Convert a CSV or Excel file to ALE format.

        Args:
            spreadsheet_path: Path to the spreadsheet
            output_path: Optional output path
            template_ale_path: Optional template ALE for header
            fps: FPS value (required)
            verbose: Enable verbose logging

        Returns:
            Path to the created ALE file
        """
        # Validate FPS
        is_valid, message = FPSValidator.validate_fps(fps, strict=False)
        if not is_valid:
            raise ValueError(message)
        elif message:  # Warning
            if verbose:
                print(message)

        # Determine output path
        if output_path is None:
            output_path = spreadsheet_path.with_suffix('.ale')

        # Use the SpreadsheetWriter method
        return SpreadsheetWriter.convert_spreadsheet_to_ale(
            spreadsheet_path, output_path, fps, template_ale_path, verbose=verbose
        )


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Convert and merge ALE files with database data',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Define valid FPS values
    valid_fps_values = FPSValidator.list_valid_fps()

    # Add subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Parser for merge command
    merge_parser = subparsers.add_parser('merge', help='Merge ALE with database')
    merge_parser.add_argument('--ale', required=True, help='Path to the ALE file')
    merge_parser.add_argument('--db', required=True, help='Path to the database CSV/Excel file')
    merge_parser.add_argument('--output', help='Path for the output ALE file')
    merge_parser.add_argument(
        '--fps', type=float, choices=valid_fps_values, default=23.976,
        help='Frames per second setting (default: 23.976)'
    )
    merge_parser.add_argument('--custom-columns', help='Path to JSON file with custom column mappings')
    merge_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose debug output')
    merge_parser.add_argument(
        '--id-position', type=int,
        help='Manually set which component of filename to use as ID (0-based)'
    )

    # Parser for export command
    export_parser = subparsers.add_parser('export', help='Export ALE to CSV/Excel')
    export_parser.add_argument('--ale', required=True, help='Path to the ALE file')
    export_parser.add_argument('--output', help='Path for the output file')
    export_parser.add_argument(
        '--format', choices=['csv', 'excel'], default='csv',
        help='Output format (default: csv)'
    )
    export_parser.add_argument(
        '--fps', type=float, choices=valid_fps_values, default=23.976,
        help='Frames per second setting (default: 23.976)'
    )

    # Parser for convert command
    convert_parser = subparsers.add_parser('convert', help='Convert CSV/Excel to ALE')
    convert_parser.add_argument('--spreadsheet', required=True, help='Path to the CSV/Excel file')
    convert_parser.add_argument('--output', help='Path for the output ALE file')
    convert_parser.add_argument('--template', help='Path to a template ALE file for header structure')
    convert_parser.add_argument(
        '--fps', type=float, choices=valid_fps_values, required=True,
        help='Frames per second setting (REQUIRED)'
    )
    convert_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose debug output')

    return parser.parse_args()


def run_merge_command(args):
    """Run the merge functionality."""
    try:
        # Load custom column mappings if provided
        column_mapper = None
        if hasattr(args, 'custom_columns') and args.custom_columns:
            column_mapper = ColumnMapper.from_json_file(Path(args.custom_columns))
            if args.verbose:
                print(f"Loaded custom column mappings: {column_mapper}")

        # Create converter instance
        converter = ALEConverter(
            ale_path=args.ale,
            db_path=args.db,
            output_path=args.output,
            verbose=args.verbose
        )

        # Get ID position if specified
        id_position = None
        if hasattr(args, 'id_position') and args.id_position is not None:
            id_position = args.id_position

        # Run conversion
        output_path = converter.convert_with_merge(
            column_mapper=column_mapper,
            id_position=id_position
        )

        print(f"\nConversion complete. Output file: {output_path}")

    except Exception as e:
        print(f"Error during merge: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def main():
    """Main function to run the conversion process."""
    args = parse_arguments()

    # Check if we're using subcommands
    if not hasattr(args, 'command') or not args.command:
        print("Error: Please specify a command (merge, export, or convert)")
        print("Use --help for more information")
        sys.exit(1)

    try:
        if args.command == 'merge':
            run_merge_command(args)

        elif args.command == 'export':
            output_path = ALEConverter.export_ale_to_spreadsheet(
                ale_path=Path(args.ale),
                output_path=Path(args.output) if args.output else None,
                format=args.format,
                fps=args.fps,
                verbose=getattr(args, 'verbose', False)
            )
            print(f"\nExport complete. Output file: {output_path}")

        elif args.command == 'convert':
            output_path = ALEConverter.convert_spreadsheet_to_ale(
                spreadsheet_path=Path(args.spreadsheet),
                output_path=Path(args.output) if args.output else None,
                template_ale_path=Path(args.template) if hasattr(args, 'template') and args.template else None,
                fps=args.fps,
                verbose=args.verbose
            )
            print(f"\nConversion complete. Output file: {output_path}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
