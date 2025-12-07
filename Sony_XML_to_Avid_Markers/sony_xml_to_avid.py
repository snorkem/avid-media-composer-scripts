#!/usr/bin/env python3
"""
Sony XML to Avid Markers Converter

Command-line tool to convert Sony camera XML metadata files to Avid marker format.

Usage:
    python sony_xml_to_avid.py /path/to/xml/files [options]

Examples:
    # Process all XML files in a directory
    python sony_xml_to_avid.py /path/to/xml/files

    # Process with custom output directory
    python sony_xml_to_avid.py /path/to/xml/files --output /path/to/output

    # Specify user name for markers
    python sony_xml_to_avid.py /path/to/xml/files --user alex

    # Enable verbose logging
    python sony_xml_to_avid.py /path/to/xml/files --verbose
"""

import argparse
import sys
from pathlib import Path
from src.sony_core import SonyXMLConverter


def main():
    parser = argparse.ArgumentParser(
        description='Convert Sony camera XML files to Avid marker format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all XML files in a directory
  python sony_xml_to_avid.py /path/to/xml/files

  # Process with custom output directory
  python sony_xml_to_avid.py /path/to/xml/files --output /path/to/output

  # Specify user name for markers
  python sony_xml_to_avid.py /path/to/xml/files --user alex

  # Enable verbose logging
  python sony_xml_to_avid.py /path/to/xml/files --verbose
        """
    )

    parser.add_argument('input_dir', type=str,
                        help='Directory containing Sony XML files')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output directory (default: same as input)')
    parser.add_argument('--user', '-u', type=str, default=None,
                        help='Username for marker entries (default: XML filename without extension)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging')
    parser.add_argument('--recursive', '-r', action='store_true',
                        help='Recursively search subdirectories for XML files')

    args = parser.parse_args()

    # Validate input directory
    input_path = Path(args.input_dir)
    if not input_path.exists():
        print(f"Error: '{args.input_dir}' does not exist")
        sys.exit(1)
    if not input_path.is_dir():
        print(f"Error: '{args.input_dir}' is not a directory")
        sys.exit(1)

    # Set output directory
    output_path = Path(args.output) if args.output else input_path

    # Run converter
    try:
        converter = SonyXMLConverter(
            input_dir=input_path,
            output_dir=output_path,
            username=args.user,
            verbose=args.verbose,
            recursive=args.recursive
        )

        stats = converter.convert_all()

        # Exit with appropriate code
        if stats['failed'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\nConversion interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
