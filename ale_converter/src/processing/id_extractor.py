"""
ID extraction functionality for matching ALE clips with database records.

This module provides methods to extract archival IDs from clip names and
database records to enable proper data matching and merging.
"""

from typing import Optional, Set
import pandas as pd


class IDExtractor:
    """
    Extracts and processes archival IDs for data matching.

    This class provides methods to extract IDs from both ALE clip names
    and database records, with support for various naming conventions.
    """

    @staticmethod
    def extract_database_ids(
        df: pd.DataFrame,
        id_column: str = 'NUMBER',
        verbose: bool = False
    ) -> pd.DataFrame:
        """
        Extract archival IDs from database.

        Args:
            df: Database DataFrame
            id_column: Name of the column containing IDs
            verbose: Enable verbose logging

        Returns:
            DataFrame with ARC_ID column added
        """
        if verbose:
            print("Extracting archival IDs from database")

        df_result = df.copy()

        # Check if ID column exists
        if id_column not in df_result.columns:
            if verbose:
                print(f"Warning: '{id_column}' column not found. Available columns:")
                print(", ".join(df_result.columns))
                print("Using first column as ID column")
            id_column = df_result.columns[0]

        # Use specified column as ARC_ID
        df_result["ARC_ID"] = df_result[id_column].astype(str)

        # Print sample IDs for debugging
        if verbose:
            sample_ids = df_result['ARC_ID'].iloc[:3].tolist() if len(df_result) >= 3 else df_result['ARC_ID'].tolist()
            print(f"Sample database IDs: {sample_ids}")

            # Check if IDs look valid
            if all(not id or id.isspace() for id in sample_ids):
                print(f"Warning: Database IDs appear to be empty. Check the {id_column} column.")

        return df_result

    @staticmethod
    def extract_ale_ids(
        df: pd.DataFrame,
        position: Optional[int] = None,
        delimiter: str = '_',
        verbose: bool = False
    ) -> pd.DataFrame:
        """
        Extract archival IDs from ALE clip names.

        This method extracts IDs by splitting clip names on a delimiter
        and taking a specific component.

        Args:
            df: ALE DataFrame with 'Name' column
            position: Position of ID in split name (0-based). If None, uses position 1
            delimiter: Character to split names on (default: '_')
            verbose: Enable verbose logging

        Returns:
            DataFrame with ARC_ID column added

        Raises:
            ValueError: If 'Name' column is not present
        """
        if verbose:
            print("Extracting archival IDs from ALE clip names")

        if 'Name' not in df.columns:
            raise ValueError("DataFrame must have a 'Name' column")

        df_result = df.copy()

        # Ensure Name column isn't NaN
        df_result["Name"] = df_result["Name"].fillna('')

        # Print sample names for debugging
        if verbose:
            sample_names = df_result['Name'].iloc[:3].tolist()
            print(f"Sample clip names: {sample_names}")

        # Use position 1 (second component) as default
        if position is None:
            position = 1

        # Split the name by delimiter
        max_splits = position + 1
        id_prep = pd.DataFrame(
            df_result["Name"].str.split(delimiter, n=max_splits, expand=True).values,
            columns=[f'col{i}' for i in range(max_splits + 1)]
        )

        # Use the specified component as the ARC_ID
        col_name = f'col{position}'
        if col_name in id_prep.columns:
            arc_id = id_prep[col_name]
        else:
            # Fall back to using the full name
            if verbose:
                print(f"Warning: Position {position} not available in split names. Using full name.")
            arc_id = df_result["Name"]

        # Check if ARC_ID column already exists
        if 'ARC_ID' in df_result.columns:
            df_result['ARC_ID'] = arc_id
        else:
            df_result.insert(0, 'ARC_ID', arc_id)

        # Print sample IDs for debugging
        if verbose:
            sample_ids = df_result['ARC_ID'].iloc[:3].tolist()
            print(f"Sample extracted IDs: {sample_ids}")

            # Print sample of name to ID mapping
            print("Sample name to ID mapping:")
            for i in range(min(3, len(df_result))):
                name = df_result['Name'].iloc[i]
                id_val = df_result['ARC_ID'].iloc[i]
                print(f"  {name} -> {id_val}")

        return df_result

    @staticmethod
    def try_alternative_extractions(
        df_ale: pd.DataFrame,
        db_ids: Set[str],
        delimiter: str = '_',
        verbose: bool = False
    ) -> Optional[pd.DataFrame]:
        """
        Try alternative ID extraction methods to find matches.

        This method attempts different positions in the filename to extract
        IDs, testing each against the database IDs to find the best match.

        Args:
            df_ale: ALE DataFrame with 'Name' column
            db_ids: Set of valid IDs from the database
            delimiter: Character to split names on
            verbose: Enable verbose logging

        Returns:
            DataFrame with best matching ARC_ID column, or None if no matches found
        """
        if verbose:
            print("Trying alternative ID extraction methods")

        # Try different parts of the name (positions 0, 2, 3)
        for part_index in [0, 2, 3]:
            if verbose:
                print(f"Trying name part {part_index} as ID")

            df_test = IDExtractor.extract_ale_ids(
                df_ale, position=part_index, delimiter=delimiter, verbose=False
            )

            # Check for overlap with database IDs
            ale_ids = set(df_test['ARC_ID'].dropna().unique())
            common_ids = ale_ids.intersection(db_ids)

            if common_ids:
                if verbose:
                    print(f"Found {len(common_ids)} matching IDs using position {part_index}")
                return df_test

        # Try using the entire name as ID
        if verbose:
            print("Trying full name as ID")

        df_result = df_ale.copy()
        df_result['ARC_ID'] = df_result['Name']

        # Check for overlap
        ale_ids = set(df_result['ARC_ID'].dropna().unique())
        common_ids = ale_ids.intersection(db_ids)

        if common_ids:
            if verbose:
                print(f"Found {len(common_ids)} matching IDs using full name")
            return df_result

        if verbose:
            print("Could not find a matching ID strategy")

        return None

    @staticmethod
    def analyze_id_overlap(
        df_ale: pd.DataFrame,
        df_db: pd.DataFrame,
        verbose: bool = False
    ) -> dict:
        """
        Analyze the overlap between ALE and database IDs.

        Args:
            df_ale: ALE DataFrame with ARC_ID column
            df_db: Database DataFrame with ARC_ID column
            verbose: Enable verbose logging

        Returns:
            Dictionary with overlap statistics
        """
        ale_ids = set(df_ale['ARC_ID'].dropna().unique())
        db_ids = set(df_db['ARC_ID'].dropna().unique())
        common_ids = ale_ids.intersection(db_ids)

        stats = {
            'ale_unique_ids': len(ale_ids),
            'db_unique_ids': len(db_ids),
            'matching_ids': len(common_ids),
            'ale_only_ids': len(ale_ids - db_ids),
            'db_only_ids': len(db_ids - ale_ids),
            'match_rate': len(common_ids) / len(ale_ids) if ale_ids else 0
        }

        if verbose:
            print(f"Number of unique IDs in ALE: {stats['ale_unique_ids']}")
            print(f"Number of unique IDs in database: {stats['db_unique_ids']}")
            print(f"Number of matching IDs: {stats['matching_ids']}")
            print(f"Match rate: {stats['match_rate']:.1%}")
            if common_ids:
                sample = list(common_ids)[:5]
                print(f"Sample matching IDs: {sample}")
            else:
                print("No matching IDs found")

        return stats
