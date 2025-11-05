"""
Data cleaning and normalization operations.

This module provides functionality to clean and normalize data from both
ALE files and database spreadsheets to ensure compatibility with AVID systems.
"""

from typing import Dict
import pandas as pd


class DataCleaner:
    """
    Handles data cleaning and normalization operations.

    This class provides methods to clean and standardize data for use in
    ALE files, including character replacement and field length limits.
    """

    # Character replacements for AVID compatibility
    CHAR_REPLACEMENTS: Dict[str, str] = {
        '\n': ' // ',
        '\\n': ' // ',
        '\\\n': ' // ',
        '\t': ' ',
        '\u000D': ' // ',      # Carriage return
        '\u2018': '\u0027',    # Left curly apostrophe to regular apostrophe
        '\u2019': '\u0027',    # Right curly apostrophe to regular apostrophe
        '\u201C': '\u0022',    # Left curly double quotes to regular quotes
        '\u201D': '\u0022',    # Right curly double quotes to regular quotes
        '\u2013': '\u002D',    # Endash to hyphen
        '\u2026': '...',       # Ellipsis to three dots
        '・・・': '...',        # Weird spaced out ellipsis to three dots
        '\u00BE': '3/4',       # ¾ to 3/4
        '\u00BD': '1/2',       # ½ to 1/2
        '\u00BC': '1/4',       # ¼ to 1/4
        '\u00E9': 'e',         # é to e
        '🙏': '',              # Remove 'Thank You' emoji
    }

    # AVID field length limit
    MAX_FIELD_LENGTH = 253

    @staticmethod
    def clean_database(df: pd.DataFrame, verbose: bool = False) -> pd.DataFrame:
        """
        Clean and normalize database data for ALE compatibility.

        This method applies all necessary transformations to ensure the data
        is compatible with AVID systems, including:
        - Replacing NaN values with empty strings
        - Replacing illegal AVID characters
        - Trimming fields to maximum length

        Args:
            df: DataFrame to clean
            verbose: Enable verbose logging

        Returns:
            Cleaned DataFrame
        """
        if verbose:
            print("Cleaning database data")

        # Create a copy to avoid modifying the original
        df_clean = df.copy()

        # Replace NaN with empty strings
        df_clean.fillna('', inplace=True)

        # Replace illegal AVID characters
        for old_char, new_char in DataCleaner.CHAR_REPLACEMENTS.items():
            df_clean = df_clean.replace(old_char, new_char, regex=True)

        # Trim columns to AVID maximum field length
        df_clean = df_clean.astype(str).apply(
            lambda x: x.str.slice(0, DataCleaner.MAX_FIELD_LENGTH)
        )

        if verbose:
            print(f"Cleaned {len(df_clean)} rows with {len(df_clean.columns)} columns")

        return df_clean

    @staticmethod
    def clean_ale_data(df: pd.DataFrame, verbose: bool = False) -> pd.DataFrame:
        """
        Clean and normalize ALE data.

        This method performs basic cleaning on ALE data including:
        - Dropping unnamed columns
        - Replacing NaN values
        - Removing newlines

        Args:
            df: DataFrame to clean
            verbose: Enable verbose logging

        Returns:
            Cleaned DataFrame
        """
        if verbose:
            print("Cleaning ALE data")

        # Create a copy
        df_clean = df.copy()

        # Drop blank/unnamed columns
        df_clean = df_clean[df_clean.columns.drop(list(df_clean.filter(regex='Unnamed')))]

        # Replace empty cells with empty strings
        df_clean.fillna('', inplace=True)

        # Remove newlines
        df_clean = df_clean.replace('\n', '', regex=True)

        if verbose:
            print(f"Cleaned ALE data: {len(df_clean)} rows, {len(df_clean.columns)} columns")

        return df_clean

    @staticmethod
    def validate_field_lengths(df: pd.DataFrame) -> Dict[str, int]:
        """
        Check for fields that exceed AVID's maximum length.

        Args:
            df: DataFrame to validate

        Returns:
            Dictionary mapping column names to count of oversized values
        """
        oversized = {}

        for col in df.columns:
            # Count values exceeding max length
            count = (df[col].astype(str).str.len() > DataCleaner.MAX_FIELD_LENGTH).sum()
            if count > 0:
                oversized[col] = count

        return oversized

    @staticmethod
    def sanitize_value(value: str) -> str:
        """
        Sanitize a single value for AVID compatibility.

        Args:
            value: String value to sanitize

        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            value = str(value)

        # Apply character replacements
        for old_char, new_char in DataCleaner.CHAR_REPLACEMENTS.items():
            value = value.replace(old_char, new_char)

        # Trim to maximum length
        if len(value) > DataCleaner.MAX_FIELD_LENGTH:
            value = value[:DataCleaner.MAX_FIELD_LENGTH]

        return value
