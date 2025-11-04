"""
MediaSilo to Avid Marker Conversion - Core shared functionality

This module contains shared constants, functions, and logic used by both
the CLI and GUI versions of the MediaSilo to Avid marker converter.
"""

import pandas as pd


# Constants for Avid marker format
MARKER_TRACK = 'V1'
MARKER_COLOR = 'Red'
MARKER_DURATION = '1'

# Columns to remove from MediaSilo CSV
COLUMNS_TO_REMOVE = ['AssetId', 'FileName', 'Created', 'Username']


def sanitize_text(text):
    """
    Sanitize text for Avid marker format by replacing problematic characters.

    Args:
        text: Input text string

    Returns:
        Sanitized text safe for tab-delimited format
    """
    if not text:
        return ''
    text = str(text)
    # Replace tabs with spaces to preserve tab-delimited format
    text = text.replace('\t', '    ')
    # Replace newlines with spaces to keep single-line format
    text = text.replace('\n', ' ').replace('\r', ' ')
    # Collapse multiple spaces into one
    text = ' '.join(text.split())
    return text


def combine_duplicate_timecodes(df, log_callback=None):
    """
    Combine entries with the same timecode into single markers.
    Uses pandas groupby for optimized performance.

    Args:
        df: DataFrame with marker data
        log_callback: Optional function(message, level='info') for logging
                     level can be 'info' or 'debug'

    Returns:
        DataFrame with combined entries
    """
    def log(message, level='info'):
        """Internal logging helper"""
        if log_callback:
            log_callback(message, level)

    log("Checking for duplicate timecodes...")

    # Use pandas groupby for better performance (vectorized operation)
    timecode_groups = df.groupby('Timecode', dropna=False)

    # Identify duplicates
    duplicate_counts = timecode_groups.size()
    duplicates = duplicate_counts[duplicate_counts > 1]

    if len(duplicates) > 0:
        log(f"Found {len(duplicates)} timecodes with multiple entries")
        for timecode, count in duplicates.items():
            log(f"  Timecode {timecode}: {count} entries", 'debug')
    else:
        log("No duplicate timecodes found")
        return df

    # Process each group
    combined_rows = []

    for timecode, group_df in timecode_groups:
        if len(group_df) == 1:
            # Single entry, keep as is
            combined_rows.append(group_df.iloc[0])
        else:
            # Multiple entries, combine them
            combined_row = group_df.iloc[0].copy()

            # Combine all comments with pipe separator
            if 'Comment' in group_df.columns:
                comments = group_df['Comment'].dropna().astype(str).str.strip()
                comments = comments[comments != '']
                combined_row['Comment'] = ' | '.join(comments) if len(comments) > 0 else ''

            # Combine names if multiple different names exist
            if 'Name' in group_df.columns:
                names = group_df['Name'].dropna().astype(str).str.strip()
                names = names[names != '']
                unique_names = names.unique()

                if len(unique_names) > 1:
                    combined_row['Name'] = ', '.join(sorted(unique_names))
                    log(f"  Combined names at {timecode}: {combined_row['Name']}", 'debug')

            log(f"  Combined {len(group_df)} entries at {timecode}", 'debug')
            combined_rows.append(combined_row)

    # Create new DataFrame from combined rows
    combined_df = pd.DataFrame(combined_rows)
    combined_df.reset_index(drop=True, inplace=True)

    log(f"Reduced from {len(df)} to {len(combined_df)} entries after combining duplicates")

    return combined_df


def sanitize_comments(df, log_callback=None):
    """
    Sanitize Comment column by replacing colons with double dashes.

    Args:
        df: DataFrame with potential Comment column
        log_callback: Optional function(message, level='info') for logging

    Returns:
        DataFrame with sanitized comments
    """
    def log(message, level='info'):
        """Internal logging helper"""
        if log_callback:
            log_callback(message, level)

    if 'Comment' in df.columns:
        # Count modifications before making changes (more efficient than copying)
        modified_count = df['Comment'].astype(str).str.contains(':', na=False).sum()

        # Replace colons with double dashes
        df['Comment'] = df['Comment'].fillna('').astype(str).str.replace(':', '--', regex=False)

        log(f"Sanitized Comment column: replaced ':' with '--' in {modified_count} entries")

    return df


def remove_unwanted_columns(df, log_callback=None):
    """
    Remove unwanted columns from the DataFrame.

    Args:
        df: DataFrame to process
        log_callback: Optional function(message, level='info') for logging

    Returns:
        DataFrame with columns removed
    """
    def log(message, level='info'):
        """Internal logging helper"""
        if log_callback:
            log_callback(message, level)

    # Drop columns (errors='ignore' handles missing columns automatically)
    existing_columns = [col for col in COLUMNS_TO_REMOVE if col in df.columns]
    df = df.drop(columns=COLUMNS_TO_REMOVE, errors='ignore')

    if existing_columns:
        log(f"Removed columns: {existing_columns}")

    return df


def format_marker_line(row):
    """
    Format a single marker row to Avid format string.

    Args:
        row: Pandas Series representing a marker row

    Returns:
        Formatted marker line string
    """
    name = str(row.get('Name', 'user')).lower().replace(' ', '').replace(',', '')
    timecode = row.get('Timecode', '00:00:00:00')
    comment = sanitize_text(row.get('Comment', ''))

    return f"{name}\t{timecode}\t{MARKER_TRACK}\t{MARKER_COLOR}\t{comment}\t{MARKER_DURATION}\t\t{MARKER_COLOR}\n"


def validate_required_columns(df, log_callback=None):
    """
    Validate that DataFrame has required columns.

    Args:
        df: DataFrame to validate
        log_callback: Optional function(message, level='info') for logging

    Returns:
        Tuple of (is_valid, missing_columns, missing_optional)
    """
    def log(message, level='info'):
        """Internal logging helper"""
        if log_callback:
            log_callback(message, level)

    required_columns = ['Timecode']
    optional_columns = ['Name', 'Comment']

    missing_required = [col for col in required_columns if col not in df.columns]
    missing_optional = [col for col in optional_columns if col not in df.columns]

    if missing_required:
        log(f"ERROR: CSV is missing required columns: {', '.join(missing_required)}")

    if missing_optional:
        log(f"Warning: Optional columns not found: {', '.join(missing_optional)}")
        log("Default values will be used for missing columns")

    return (len(missing_required) == 0, missing_required, missing_optional)
