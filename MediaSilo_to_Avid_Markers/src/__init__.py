"""
MediaSilo to Avid Marker Conversion Package

This package provides shared functionality for converting MediaSilo CSV exports
to Avid marker text format.
"""

from .mediasilo_core import (
    # Constants
    MARKER_TRACK,
    MARKER_COLOR,
    MARKER_DURATION,
    COLUMNS_TO_REMOVE,

    # Functions
    sanitize_text,
    combine_duplicate_timecodes,
    sanitize_comments,
    remove_unwanted_columns,
    format_marker_line,
    validate_required_columns
)

__all__ = [
    # Constants
    'MARKER_TRACK',
    'MARKER_COLOR',
    'MARKER_DURATION',
    'COLUMNS_TO_REMOVE',

    # Functions
    'sanitize_text',
    'combine_duplicate_timecodes',
    'sanitize_comments',
    'remove_unwanted_columns',
    'format_marker_line',
    'validate_required_columns'
]

__version__ = '1.0.0'
