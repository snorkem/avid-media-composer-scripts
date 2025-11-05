"""
Data models for ALE file structures.

This module defines data classes that represent ALE file components including
headers and data sections.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import pandas as pd


@dataclass
class ALEHeader:
    """
    Represents the header section of an ALE file.

    The header contains metadata about the ALE file format, including
    field delimiters, video/audio formats, and frame rate information.

    Attributes:
        field_delim: Field delimiter type (e.g., 'TABS')
        video_format: Video format specification (e.g., '1080')
        audio_format: Audio format specification (e.g., '48khz')
        fps: Frames per second (e.g., 23.976, 29.97)
        custom_fields: Additional custom header fields
    """

    field_delim: str = "TABS"
    video_format: str = "1080"
    audio_format: str = "48khz"
    fps: float = 23.976
    custom_fields: Dict[str, str] = field(default_factory=dict)

    def to_string(self) -> str:
        """
        Convert the header to ALE file format string.

        Returns:
            Formatted header string ready for ALE file output
        """
        lines = ["Heading"]
        lines.append(f"FIELD_DELIM\t{self.field_delim}")
        lines.append(f"VIDEO_FORMAT\t{self.video_format}")
        lines.append(f"AUDIO_FORMAT\t{self.audio_format}")
        lines.append(f"FPS\t{self.fps}")

        # Add any custom fields
        for key, value in self.custom_fields.items():
            lines.append(f"{key}\t{value}")

        return "\n".join(lines)

    @classmethod
    def from_string(cls, header_text: str) -> 'ALEHeader':
        """
        Parse an ALE header from text.

        Args:
            header_text: Raw header text from ALE file

        Returns:
            ALEHeader instance populated from the text
        """
        import re

        # Initialize with defaults
        field_delim = "TABS"
        video_format = "1080"
        audio_format = "48khz"
        fps = 23.976
        custom_fields = {}

        # Parse header lines
        lines = header_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line or line == "Heading":
                continue

            # Split on tab
            parts = line.split('\t', 1)
            if len(parts) != 2:
                continue

            key, value = parts
            key = key.strip()
            value = value.strip()

            # Map known fields
            if key == "FIELD_DELIM":
                field_delim = value
            elif key == "VIDEO_FORMAT":
                video_format = value
            elif key == "AUDIO_FORMAT":
                audio_format = value
            elif key == "FPS":
                try:
                    fps = float(value)
                except ValueError:
                    pass
            else:
                # Store as custom field
                custom_fields[key] = value

        return cls(
            field_delim=field_delim,
            video_format=video_format,
            audio_format=audio_format,
            fps=fps,
            custom_fields=custom_fields
        )


@dataclass
class ALEData:
    """
    Represents a complete ALE file with header and data.

    This class encapsulates both the metadata (header) and the actual
    clip data contained in an ALE file.

    Attributes:
        header: ALEHeader instance containing file metadata
        data: Pandas DataFrame containing clip data
        column_names: List of column names (derived from DataFrame)
    """

    header: ALEHeader
    data: pd.DataFrame

    @property
    def column_names(self) -> List[str]:
        """Get list of column names from the data DataFrame."""
        return self.data.columns.tolist()

    @property
    def num_clips(self) -> int:
        """Get the number of clips in the ALE data."""
        return len(self.data)

    def get_sample_values(self, column: str, n: int = 5) -> List[str]:
        """
        Get sample values from a specific column.

        Args:
            column: Column name to sample from
            n: Number of samples to return

        Returns:
            List of sample values from the column
        """
        if column not in self.data.columns:
            return []

        return self.data[column].iloc[:n].tolist()

    def add_column(self, column_name: str, values: pd.Series, position: Optional[int] = None) -> None:
        """
        Add a new column to the data.

        Args:
            column_name: Name of the new column
            values: Pandas Series with values for the column
            position: Optional position to insert the column (0-based index)
        """
        if position is not None:
            self.data.insert(position, column_name, values)
        else:
            self.data[column_name] = values

    def drop_columns(self, columns: List[str]) -> None:
        """
        Drop specified columns from the data.

        Args:
            columns: List of column names to drop
        """
        existing_columns = [col for col in columns if col in self.data.columns]
        if existing_columns:
            self.data.drop(columns=existing_columns, inplace=True)

    def rename_columns(self, mapping: Dict[str, str]) -> None:
        """
        Rename columns according to provided mapping.

        Args:
            mapping: Dictionary mapping old column names to new names
        """
        # Only rename columns that exist
        valid_mapping = {
            old: new for old, new in mapping.items()
            if old in self.data.columns
        }
        if valid_mapping:
            self.data.rename(columns=valid_mapping, inplace=True)

    @classmethod
    def create_empty(cls, header: Optional[ALEHeader] = None) -> 'ALEData':
        """
        Create an empty ALEData instance.

        Args:
            header: Optional ALEHeader to use, otherwise creates default

        Returns:
            Empty ALEData instance
        """
        if header is None:
            header = ALEHeader()

        return cls(header=header, data=pd.DataFrame())
