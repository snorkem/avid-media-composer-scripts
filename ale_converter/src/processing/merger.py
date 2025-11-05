"""
Data merging functionality for combining ALE and database data.

This module handles the merging of ALE clip data with database metadata
based on matching archival IDs.
"""

from typing import Dict, List, Optional
import pandas as pd


class DataMerger:
    """
    Merges ALE data with database metadata.

    This class provides methods to combine ALE clip data with database
    records based on archival IDs, with support for column filtering
    and renaming.
    """

    @staticmethod
    def merge_data(
        df_ale: pd.DataFrame,
        df_db: pd.DataFrame,
        ale_columns: Optional[List[str]] = None,
        verbose: bool = False
    ) -> pd.DataFrame:
        """
        Merge ALE data with database data based on archival IDs.

        Args:
            df_ale: ALE DataFrame with ARC_ID column
            df_db: Database DataFrame with ARC_ID column
            ale_columns: Optional list of ALE columns to include in merge
            verbose: Enable verbose logging

        Returns:
            Merged DataFrame

        Raises:
            ValueError: If ARC_ID column is missing from either DataFrame
        """
        if verbose:
            print("Merging ALE with database")

        # Validate that both DataFrames have ARC_ID
        if 'ARC_ID' not in df_ale.columns:
            raise ValueError("ALE DataFrame must have 'ARC_ID' column")
        if 'ARC_ID' not in df_db.columns:
            raise ValueError("Database DataFrame must have 'ARC_ID' column")

        # Select columns to merge from ALE
        if ale_columns is None:
            ale_columns = ['ARC_ID', 'Name', 'Start', 'End', 'Tape', 'Source File']

        # Filter to only existing columns
        selected_ale_columns = [col for col in ale_columns if col in df_ale.columns]

        if verbose:
            print(f"ALE columns for merge: {selected_ale_columns}")
            print(f"Database columns: {len(df_db.columns)}")

        # Perform the merge
        df_merged = df_ale[selected_ale_columns].merge(
            df_db, how='left', on=['ARC_ID']
        )

        if verbose:
            print(f"Merged data has {len(df_merged)} rows and {len(df_merged.columns)} columns")

            # Check for null values in key columns
            key_columns = ['DATE', 'BRIEF DESCRIPTION', 'LONG DESCRIPTION', 'VENDOR']
            for col in key_columns:
                if col in df_merged.columns:
                    null_count = df_merged[col].isna().sum()
                    print(f"Column '{col}' has {null_count} null values out of {len(df_merged)} rows")

                    # Show sample values
                    if len(df_merged) > 0:
                        sample_values = df_merged[col].dropna().iloc[:3].tolist()
                        if sample_values:
                            print(f"  Sample values: {sample_values}")

        return df_merged

    @staticmethod
    def prepare_for_ale_output(
        df_merged: pd.DataFrame,
        columns_to_drop: Optional[List[str]] = None,
        columns_to_rename: Optional[Dict[str, str]] = None,
        add_null_row: bool = False,
        verbose: bool = False
    ) -> pd.DataFrame:
        """
        Prepare merged data for ALE output.

        This method filters and renames columns according to specifications,
        preparing the data for writing to an ALE file.

        Args:
            df_merged: Merged DataFrame
            columns_to_drop: List of column names to exclude
            columns_to_rename: Dictionary mapping old names to new names
            add_null_row: Whether to add a "null" row at the end
            verbose: Enable verbose logging

        Returns:
            Prepared DataFrame ready for ALE output
        """
        if verbose:
            print("Preparing data for ALE output")

        # Create a copy to avoid modifying original
        df_output = df_merged.copy()

        # Apply default column drops if not specified
        if columns_to_drop is None:
            columns_to_drop = DataMerger._get_default_columns_to_drop(df_output)

        # Apply default renames if not specified
        if columns_to_rename is None:
            columns_to_rename = DataMerger._get_default_column_renames()

        if verbose:
            print(f"Columns to drop: {len(columns_to_drop)}")
            print(f"Columns to rename: {len(columns_to_rename)}")

        # Drop specified columns
        existing_drops = [col for col in columns_to_drop if col in df_output.columns]
        if existing_drops:
            df_output = df_output.drop(columns=existing_drops, errors='ignore')

        # Rename columns
        valid_renames = {
            old: new for old, new in columns_to_rename.items()
            if old in df_output.columns
        }
        if valid_renames:
            df_output = df_output.rename(columns=valid_renames)

        # Add null row if requested
        if add_null_row:
            null_row = pd.DataFrame([["null"] * len(df_output.columns)], columns=df_output.columns)
            df_output = pd.concat([df_output, null_row], ignore_index=True)

        if verbose:
            print(f"Final output columns ({len(df_output.columns)}):")
            for col in df_output.columns:
                print(f"  {col}")

        return df_output

    @staticmethod
    def _get_default_columns_to_drop(df: pd.DataFrame) -> List[str]:
        """
        Get default list of columns to drop from merged data.

        Args:
            df: DataFrame to analyze

        Returns:
            List of column names to drop
        """
        # Base columns to drop
        base_columns = [
            'PROJECT ID', 'VENDOR', 'SOURCE ID',
            'Image grab', 'Asset Number', 'Ingested by',
            'Ingested date', 'Transcript Status', 'Script Sync Status',
            'Rename needed', 'AE question', 'Transcription Request',
            'AMAZING CLIP'
        ]

        # Regex patterns for additional columns to drop
        regex_patterns = [
            'LINK.+', 'Asset NAME', 'Version',
            'Ingested.+', 'Transcript.+', 'Script Sync.+',
            'AE question', 'Transcription Request', 'AMAZING.+'
        ]

        columns_to_drop = base_columns.copy()

        # Add regex matches
        for pattern in regex_patterns:
            regex_matches = list(df.filter(regex=pattern).columns)
            columns_to_drop.extend(regex_matches)

        # Remove duplicates
        return list(set(columns_to_drop))

    @staticmethod
    def _get_default_column_renames() -> Dict[str, str]:
        """
        Get default column rename mapping.

        Returns:
            Dictionary mapping old column names to new names
        """
        return {
            "DATE": "Arc date",
            "BRIEF DESCRIPTION": "Brief desc",
            "LONG DESCRIPTION": "Long desc",
            "NUMBER": "Archive ID",
            "Drop Folder & Initials": "Drop folder",
            "Name_x": "Clip Name",
            "NOTES": "Comments",
            "LOCATION": "Shot Location",
            "PEOPLE": "People",
            "COPYRIGHT": "Rights Info"
        }

    @staticmethod
    def create_column_mapping(
        df_db: pd.DataFrame,
        columns_to_drop: List[str],
        columns_to_rename: Dict[str, str]
    ) -> Dict[str, Optional[str]]:
        """
        Create a mapping showing how database columns transform to ALE columns.

        Args:
            df_db: Original database DataFrame
            columns_to_drop: List of columns to drop
            columns_to_rename: Dictionary of column renames

        Returns:
            Dictionary mapping database column names to ALE column names
            (None for dropped columns)
        """
        mapping = {}

        for col in df_db.columns:
            if col in columns_to_drop:
                mapping[col] = None  # Column will be dropped
            elif col in columns_to_rename:
                mapping[col] = columns_to_rename[col]  # Column will be renamed
            else:
                mapping[col] = col  # Column keeps same name

        return mapping
