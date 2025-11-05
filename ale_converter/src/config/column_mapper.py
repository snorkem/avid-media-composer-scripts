"""
Column mapping configuration management.

This module handles loading, saving, and managing column mapping configurations
for controlling how database columns are transformed for ALE output.
"""

from pathlib import Path
from typing import Dict, List, Optional
import json


class ColumnMapper:
    """
    Manages column mapping configurations.

    This class handles the loading and saving of column mapping configurations
    that control which database columns are included in ALE output and how
    they are renamed.
    """

    def __init__(
        self,
        columns_to_drop: Optional[List[str]] = None,
        columns_to_rename: Optional[Dict[str, str]] = None
    ):
        """
        Initialize the ColumnMapper.

        Args:
            columns_to_drop: List of column names to exclude from output
            columns_to_rename: Dictionary mapping old names to new names
        """
        self.columns_to_drop = columns_to_drop or []
        self.columns_to_rename = columns_to_rename or {}

    @classmethod
    def from_json_file(cls, file_path: Path) -> 'ColumnMapper':
        """
        Load column mappings from a JSON file.

        Args:
            file_path: Path to the JSON configuration file

        Returns:
            ColumnMapper instance with loaded configuration

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the JSON format is invalid
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # Validate structure
            if not isinstance(config, dict):
                raise ValueError("Configuration must be a JSON object")

            columns_to_drop = config.get('columns_to_drop', [])
            columns_to_rename = config.get('columns_to_rename', {})

            # Validate types
            if not isinstance(columns_to_drop, list):
                raise ValueError("'columns_to_drop' must be a list")
            if not isinstance(columns_to_rename, dict):
                raise ValueError("'columns_to_rename' must be an object/dictionary")

            return cls(columns_to_drop=columns_to_drop, columns_to_rename=columns_to_rename)

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")
        except Exception as e:
            raise ValueError(f"Error loading configuration: {e}")

    def to_json_file(self, file_path: Path) -> None:
        """
        Save column mappings to a JSON file.

        Args:
            file_path: Path where the configuration should be saved

        Raises:
            IOError: If the file cannot be written
        """
        config = {
            "columns_to_drop": self.columns_to_drop,
            "columns_to_rename": self.columns_to_rename
        }

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config, indent=4, fp=f)
        except Exception as e:
            raise IOError(f"Error saving configuration: {e}")

    def to_dict(self) -> Dict:
        """
        Convert the mapping to a dictionary.

        Returns:
            Dictionary with columns_to_drop and columns_to_rename
        """
        return {
            "columns_to_drop": self.columns_to_drop,
            "columns_to_rename": self.columns_to_rename
        }

    def add_drop(self, column: str) -> None:
        """
        Add a column to the drop list.

        Args:
            column: Column name to drop
        """
        if column not in self.columns_to_drop:
            self.columns_to_drop.append(column)

        # Remove from rename dict if present
        if column in self.columns_to_rename:
            del self.columns_to_rename[column]

    def add_rename(self, old_name: str, new_name: str) -> None:
        """
        Add a column rename mapping.

        Args:
            old_name: Original column name
            new_name: New column name
        """
        # Remove from drop list if present
        if old_name in self.columns_to_drop:
            self.columns_to_drop.remove(old_name)

        # Add to rename dict
        self.columns_to_rename[old_name] = new_name

    def remove_drop(self, column: str) -> None:
        """
        Remove a column from the drop list.

        Args:
            column: Column name to stop dropping
        """
        if column in self.columns_to_drop:
            self.columns_to_drop.remove(column)

    def remove_rename(self, column: str) -> None:
        """
        Remove a column from the rename mapping.

        Args:
            column: Column name to stop renaming
        """
        if column in self.columns_to_rename:
            del self.columns_to_rename[column]

    def get_mapping_for_column(self, column: str) -> Optional[str]:
        """
        Get the mapping for a specific column.

        Args:
            column: Column name to check

        Returns:
            None if column is dropped, renamed name if renamed, or original name
        """
        if column in self.columns_to_drop:
            return None
        elif column in self.columns_to_rename:
            return self.columns_to_rename[column]
        else:
            return column

    def validate_against_columns(self, available_columns: List[str]) -> Dict[str, List[str]]:
        """
        Validate the mapping against a list of available columns.

        Args:
            available_columns: List of column names to validate against

        Returns:
            Dictionary with 'invalid_drops' and 'invalid_renames' lists
        """
        invalid_drops = [
            col for col in self.columns_to_drop
            if col not in available_columns
        ]

        invalid_renames = [
            col for col in self.columns_to_rename.keys()
            if col not in available_columns
        ]

        return {
            'invalid_drops': invalid_drops,
            'invalid_renames': invalid_renames
        }

    def __repr__(self) -> str:
        """String representation of the ColumnMapper."""
        return (
            f"ColumnMapper("
            f"drops={len(self.columns_to_drop)}, "
            f"renames={len(self.columns_to_rename)})"
        )
