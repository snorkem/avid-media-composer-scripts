import pandas as pd
import sys
import logging

# Import shared functionality
from src.mediasilo_core import (
    combine_duplicate_timecodes,
    sanitize_comments, remove_unwanted_columns,
    format_marker_line, validate_required_columns
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mediasilo_conversion.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def log_callback(message, level='info'):
    """Callback for shared functions to log messages"""
    if level == 'debug':
        logger.debug(message)
    else:
        logger.info(message)


def convert_mediasilo_to_avid(input_csv_path, output_txt_path):
    """
    Convert MediaSilo CSV export to Avid marker text format.

    Args:
        input_csv_path: Path to input MediaSilo CSV file
        output_txt_path: Path to output Avid marker text file
    """
    logger.info("=" * 60)
    logger.info("Starting MediaSilo to Avid conversion")
    logger.info(f"Input file: {input_csv_path}")
    logger.info(f"Output file: {output_txt_path}")
    logger.info("=" * 60)

    try:
        # Load the CSV file into a DataFrame
        logger.info("Loading CSV file...")
        df = pd.read_csv(input_csv_path)

        logger.info(f"Loaded {len(df)} rows from {input_csv_path}")
        logger.info(f"Columns: {list(df.columns)}")

        # Validate required columns
        is_valid, missing_required, missing_optional = validate_required_columns(df, log_callback)
        if not is_valid:
            logger.error(f"CSV is missing required columns: {', '.join(missing_required)}")
            sys.exit(1)

        # Remove unwanted columns
        df = remove_unwanted_columns(df, log_callback)
        logger.info(f"Remaining columns: {list(df.columns)}")

        # Combine duplicate timecodes BEFORE sanitizing comments
        df = combine_duplicate_timecodes(df, log_callback)

        # Sanitize Comment column - replace all ":" with "--"
        df = sanitize_comments(df, log_callback)

        # Write output in Avid marker format
        logger.info("Writing Avid marker file...")
        with open(output_txt_path, 'w', encoding='utf-8') as f:
            for i, (_, row) in enumerate(df.iterrows(), start=1):
                line = format_marker_line(row)
                f.write(line)

                if i % 10 == 0:
                    logger.debug(f"Wrote {i}/{len(df)} markers...")

        logger.info(f"Successfully wrote {len(df)} markers to {output_txt_path}")
        logger.info(f"Output format: username\\ttimecode\\tV1\\tRed\\t?\\t1\\t\\tRed")
        logger.info("=" * 60)
        logger.info("Conversion completed successfully!")
        logger.info("=" * 60)

    except FileNotFoundError:
        logger.error(f"Could not find input file '{input_csv_path}'")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Check for command line arguments
    if len(sys.argv) != 3:
        print("Usage: python script.py <input_csv_file> <output_txt_file>")
        print("\nExample:")
        print("  python script.py MediaSilo_export.csv Avid_markers.txt")
        print("\nNote: A log file 'mediasilo_conversion.log' will be created")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    convert_mediasilo_to_avid(input_file, output_file)
