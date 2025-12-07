"""
Sony XML to Avid Marker Conversion - Core functionality

Converts Sony camera XML metadata files to Avid marker format.
Extracts KlvPacket markers and converts timecodes using frame offsets.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path

from timecode import Timecode

# ============================================================================
# Module Constants
# ============================================================================

# Sony XML namespace
SONY_NAMESPACE = {"ns": "urn:schemas-professionalDisc:nonRealTimeMeta:ver.2.20"}

# Avid marker output constants
AVID_TRACK = "V1"
AVID_DURATION = "1"

# Frame rate mapping for Sony formatFps strings
FPS_MAP = {
    "23.98": 23.976,
    "29.97": 29.97,
    "59.94": 59.94,
}


# ============================================================================
# Hex Decoding Functions
# ============================================================================

def hex_to_timecode(hex_str: str) -> str:
    """
    Convert Sony hex timecode to HH:MM:SS:FF string.

    Args:
        hex_str: 8-digit hex string (e.g., "20264709")

    Returns:
        Timecode string (e.g., "20:26:47:09")

    Example:
        "20264709" -> "20:26:47:09"

    Raises:
        ValueError: If hex string is not 8 digits
    """
    if len(hex_str) != 8:
        raise ValueError(f"Invalid hex timecode length: {len(hex_str)} (expected 8)")

    # Each pair of digits is one timecode component
    hh = hex_str[0:2]
    mm = hex_str[2:4]
    ss = hex_str[4:6]
    ff = hex_str[6:8]

    return f"{hh}:{mm}:{ss}:{ff}"


def decode_length_value(hex_str: str) -> str:
    """
    Decode Sony KlvPacket lengthValue from hex to text.

    Format: First 2 hex digits = byte length, rest = UTF-8 encoded text

    Args:
        hex_str: Hex string (e.g., "0A5F53686F744D61726B31")

    Returns:
        Decoded text (e.g., "_ShotMark1")

    Example:
        "0A5F53686F744D61726B31" -> "_ShotMark1"
        0A = length 10 bytes
        5F53686F744D61726B31 = "_ShotMark1" in UTF-8

    Raises:
        ValueError: If hex string is too short or cannot be decoded
    """
    if len(hex_str) < 2:
        raise ValueError("lengthValue too short")

    # Remaining digits are UTF-8 encoded text (skip first 2 length bytes)
    text_hex = hex_str[2:]

    # Convert hex pairs to bytes
    try:
        byte_data = bytes.fromhex(text_hex)
        return byte_data.decode("utf-8")
    except (ValueError, UnicodeDecodeError) as e:
        raise ValueError(f"Error decoding lengthValue: {e}") from e


# ============================================================================
# Frame Rate Parsing
# ============================================================================

def parse_format_fps(format_fps_str: str) -> float:
    """
    Parse Sony formatFps string to numeric frame rate.

    Args:
        format_fps_str: Frame rate string from VideoFrame element (e.g., "23.98p", "24p")

    Returns:
        Float frame rate (e.g., 23.976, 24.0)

    Examples:
        "23.98p" -> 23.976
        "24p" -> 24.0
        "29.97p" -> 29.97
        "59.94p" -> 59.94
        "25p" -> 25.0

    Raises:
        ValueError: If format string is not recognized
    """
    # Remove 'p' or 'P' suffix if present (Python 3.9+)
    fps_str = format_fps_str.removesuffix("p").removesuffix("P")

    # Map common values to precise frame rates using module constant
    if fps_str in FPS_MAP:
        return FPS_MAP[fps_str]

    # Try direct conversion for other values (24, 25, 30, 50, 60, etc.)
    try:
        return float(fps_str)
    except ValueError as e:
        raise ValueError(f"Unrecognized formatFps value: '{format_fps_str}'") from e


# ============================================================================
# Timecode Calculation
# ============================================================================

def calculate_marker_timecode(start_tc_str: str, frame_offset: int, fps: float) -> str:
    """
    Calculate marker timecode by adding frame offset to start timecode.

    Uses Python timecode module for accurate frame arithmetic.

    Args:
        start_tc_str: Start timecode as "HH:MM:SS:FF"
        frame_offset: Number of frames to add
        fps: Frame rate (e.g., 24)

    Returns:
        Timecode string in "HH:MM:SS:FF" format

    Example:
        start = "20:26:47:09"
        offset = 59 frames
        fps = 24
        result = "20:26:49:20"  # 59 frames = 2 seconds 11 frames at 24fps
    """
    # Create Timecode object from start timecode
    tc = Timecode(fps, start_timecode=start_tc_str)

    # Add frame offset
    tc += frame_offset

    # Return as string in HH:MM:SS:FF format
    return str(tc)


# ============================================================================
# Marker Processing
# ============================================================================

def filter_shot_markers(
    markers: list[dict], log_callback: Callable[[str], None] | None = None
) -> list[dict]:
    """
    Filter markers to include only _ShotMark entries.

    Excludes: _RecStart and any other marker types
    Includes: _ShotMark1, _ShotMark2, etc.

    Args:
        markers: List of marker dicts with 'text' field
        log_callback: Optional logging function

    Returns:
        Filtered list of markers
    """
    shot_markers = [m for m in markers if m["text"].startswith("_ShotMark")]

    excluded_count = len(markers) - len(shot_markers)
    if excluded_count > 0 and log_callback:
        log_callback(f"Filtered out {excluded_count} non-ShotMark entries")

    return shot_markers


def determine_marker_color(length_value_hex: str) -> str:
    """
    Determine Avid marker color based on lengthValue hex string.

    Rules:
        - Green: lengthValue ends with "32" (hex for ASCII '2')
        - Blue: lengthValue ends with "31" (hex for ASCII '1')
        - Red: default (all other cases)

    Args:
        length_value_hex: Hex string from KlvPacket lengthValue attribute

    Returns:
        Color name: "Green", "Blue", or "Red"

    Examples:
        "0A5F53686F744D61726B32" ends with "32" -> "Green"
        "0A5F53686F744D61726B31" ends with "31" -> "Blue"
        "095F5265635374617274" ends with "74" -> "Red"
    """
    # Use match/case for cleaner conditional logic (Python 3.10+)
    match length_value_hex[-2:]:
        case "32":
            return "Green"
        case "31":
            return "Blue"
        case _:
            return "Red"


# ============================================================================
# Utility Functions
# ============================================================================


def sanitize_username(username: str) -> str:
    """
    Sanitize username for Avid marker format.

    Removes Sony camera naming pattern suffix (M01) and cleans the string.

    Args:
        username: Raw username string

    Returns:
        Sanitized username (lowercase, no spaces, no M01 suffix)

    Examples:
        "A003C010_251203EHM01" -> "a003c010_251203eh"
        "Test User" -> "testuser"
    """
    # Remove "M01" suffix if present (Sony camera naming pattern)
    cleaned = username.removesuffix("M01")
    # Lowercase and remove spaces
    return cleaned.lower().replace(" ", "")


# ============================================================================
# XML Parsing
# ============================================================================


def parse_sony_xml(
    xml_path: Path, log_callback: Callable[[str], None] | None = None
) -> dict:
    """
    Parse Sony XML file and extract marker data.

    Args:
        xml_path: Path to Sony XML file
        log_callback: Optional logging function

    Returns:
        Dict with keys:
            - fps: Frame rate (float)
            - start_timecode: Start timecode as "HH:MM:SS:FF" (str)
            - markers: List of dicts with keys:
                - frameCount: Frame number (int)
                - text: Decoded marker text (str)
                - lengthValue: Original hex value (str) for color determination

    Raises:
        ValueError: If XML is malformed or missing required elements
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Extract frame rate - prefer formatFps from VideoFrame over tcFps
        ltc_table = root.find("ns:LtcChangeTable", SONY_NAMESPACE)
        if ltc_table is None:
            raise ValueError("LtcChangeTable not found in XML")

        # Validate and extract tcFps
        tc_fps_str = ltc_table.attrib.get("tcFps")
        if tc_fps_str is None:
            raise ValueError("Missing tcFps attribute in LtcChangeTable")
        try:
            tc_fps = int(tc_fps_str)
        except ValueError as e:
            raise ValueError(
                f"Invalid tcFps value: '{tc_fps_str}' (expected integer)"
            ) from e

        # Try to get actual video formatFps (more accurate)
        video_frame = root.find(".//ns:VideoFrame", SONY_NAMESPACE)
        fps = tc_fps  # Default to tcFps

        if video_frame is not None:
            format_fps_str = video_frame.attrib.get("formatFps")
            if format_fps_str:
                try:
                    format_fps = parse_format_fps(format_fps_str)

                    # Check for mismatch and warn
                    if abs(format_fps - tc_fps) > 0.01 and log_callback:
                        log_callback(
                            f"Warning: Frame rate mismatch detected - "
                            f"tcFps={tc_fps}, formatFps={format_fps_str} ({format_fps}). "
                            f"Using formatFps={format_fps} for accurate timecode calculation."
                        )

                    fps = format_fps  # Use the more accurate formatFps
                except ValueError as e:
                    if log_callback:
                        log_callback(
                            f"Warning: Could not parse formatFps '{format_fps_str}': {e}. "
                            f"Using tcFps={tc_fps}"
                        )

        # Extract start timecode
        ltc_change = root.find(".//ns:LtcChange[@frameCount='0']", SONY_NAMESPACE)
        if ltc_change is None:
            raise ValueError("Start LtcChange not found")

        start_tc_hex = ltc_change.attrib.get("value")
        if start_tc_hex is None:
            raise ValueError("Missing 'value' attribute in start LtcChange element")

        start_timecode = hex_to_timecode(start_tc_hex)

        # Extract markers
        markers = []
        klv_packets = root.findall(".//ns:KlvPacket", SONY_NAMESPACE)

        for pkt in klv_packets:
            frame_count = int(pkt.attrib["frameCount"])
            length_value = pkt.attrib["lengthValue"]
            marker_text = decode_length_value(length_value)

            markers.append({
                "frameCount": frame_count,
                "text": marker_text,
                "lengthValue": length_value,  # Keep for color determination
            })

        return {
            "fps": fps,
            "start_timecode": start_timecode,
            "markers": markers,
        }

    except ET.ParseError as e:
        raise ValueError(f"XML parsing error: {e}") from e
    except Exception as e:
        raise ValueError(f"Error parsing Sony XML: {e}") from e


# ============================================================================
# Output Generation
# ============================================================================

def generate_output_filename(input_xml_path: Path) -> str:
    """
    Generate output filename from input XML filename.

    Input:  A003C010_251203EHM01.XML
    Output: A003C010_251203EHM01_markers.txt

    Args:
        input_xml_path: Path to input XML file

    Returns:
        Output filename string
    """
    stem = input_xml_path.stem  # Removes .XML extension
    return f"{stem}_markers.txt"


def write_avid_markers(
    markers: list[dict],
    output_path: Path,
    username: str = "user",
    log_callback: Callable[[str], None] | None = None,
) -> None:
    """
    Write markers to Avid marker format text file.

    Format: <user>\t<timecode>\t<track>\t<color>\t<comment>\t<duration>\t<unused>\t<color>

    Args:
        markers: List of marker dicts with keys: timecode, text, color
        output_path: Path to output .txt file
        username: Username for marker entries
        log_callback: Optional logging function
    """
    with open(output_path, "w", encoding="utf-8") as f:
        for marker in markers:
            timecode = marker["timecode"]
            color = marker["color"]
            comment = marker["text"]

            # Format: user\tTC\tV1\tColor\tComment\t1\t\tColor\n
            line = f"{username}\t{timecode}\t{AVID_TRACK}\t{color}\t{comment}\t{AVID_DURATION}\t\t{color}\n"
            f.write(line)

    if log_callback:
        log_callback(f"Wrote {len(markers)} markers to {output_path.name}")


# ============================================================================
# File Discovery
# ============================================================================

def find_xml_files(
    directory: Path,
    recursive: bool = False,
    log_callback: Callable[[str], None] | None = None,
) -> list[Path]:
    """
    Find all Sony XML files in directory.

    Args:
        directory: Directory to search
        recursive: If True, search subdirectories recursively
        log_callback: Optional logging function

    Returns:
        List of paths to XML files, sorted by filename
    """
    # Case-insensitive search for .xml extension
    if recursive:
        # Use rglob for recursive search (case-insensitive via pattern)
        xml_files = list(directory.rglob("*.[xX][mM][lL]"))
    else:
        # Single directory search
        xml_files = [f for f in directory.iterdir() if f.suffix.lower() == ".xml"]

    if not xml_files:
        if log_callback:
            search_type = "recursively" if recursive else "in directory"
            log_callback(f"No XML files found {search_type}")
        return []

    if log_callback:
        search_type = "recursively" if recursive else ""
        log_callback(f"Found {len(xml_files)} XML files {search_type}".strip())

    return sorted(xml_files)


# ============================================================================
# Single File Processing
# ============================================================================

def process_single_xml(
    xml_path: Path,
    output_dir: Path,
    username: str | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> bool:
    """
    Process a single Sony XML file and generate Avid markers.

    Args:
        xml_path: Path to XML file
        output_dir: Directory for output file
        username: Username for markers (if None, uses XML filename without extension)
        log_callback: Optional logging function

    Returns:
        True if successful, False otherwise
    """
    try:
        # Use filename without extension if no username provided
        if username is None:
            username = xml_path.stem

        # Clean up username using helper function
        username = sanitize_username(username)

        # Parse XML
        data = parse_sony_xml(xml_path, log_callback)

        # Filter markers
        shot_markers = filter_shot_markers(data["markers"], log_callback)

        if not shot_markers:
            if log_callback:
                log_callback(f"No ShotMark entries found in {xml_path.name}")
            return True  # Not an error, just no markers

        # Convert to Avid format
        avid_markers = []
        for marker in shot_markers:
            try:
                timecode = calculate_marker_timecode(
                    data["start_timecode"],
                    marker["frameCount"],
                    data["fps"],
                )
                color = determine_marker_color(marker["lengthValue"])

                avid_markers.append({
                    "timecode": timecode,
                    "text": marker["text"],
                    "color": color,
                })
            except Exception as e:
                if log_callback:
                    log_callback(
                        f"Error processing marker at frame {marker['frameCount']}: {e}"
                    )
                continue

        if not avid_markers:
            if log_callback:
                log_callback(f"No markers generated for {xml_path.name}")
            return True

        # Write output
        output_filename = generate_output_filename(xml_path)
        output_path = output_dir / output_filename
        write_avid_markers(avid_markers, output_path, username, log_callback)

        return True

    except (FileNotFoundError, ET.ParseError, ValueError) as e:
        if log_callback:
            error_type = type(e).__name__
            log_callback(f"{error_type} in {xml_path.name}: {e}")
        return False
    except Exception as e:
        if log_callback:
            log_callback(f"Unexpected error processing {xml_path.name}: {e}")
        return False


# ============================================================================
# Main Converter Class
# ============================================================================

class SonyXMLConverter:
    """Main converter class for Sony XML to Avid markers."""

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        username: str | None = None,
        verbose: bool = False,
        recursive: bool = False,
    ) -> None:
        """
        Initialize converter.

        Args:
            input_dir: Directory containing Sony XML files
            output_dir: Directory for output marker files
            username: Username for marker entries (if None, uses XML filename without extension)
            verbose: Enable verbose logging
            recursive: Search subdirectories recursively for XML files
        """
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.username = sanitize_username(username) if username else None
        self.verbose = verbose
        self.recursive = recursive

        # Setup logging
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Configure logging based on verbosity."""
        level = logging.DEBUG if self.verbose else logging.INFO
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler("sony_xml_conversion.log"),
                logging.StreamHandler(),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def log(self, message: str, level: str = "info") -> None:
        """Internal logging helper."""
        # Use getattr for cleaner dispatch
        log_method = getattr(self.logger, level, self.logger.info)
        log_method(message)

    def convert_all(self) -> dict[str, int]:
        """
        Process all XML files in input directory.

        Returns:
            Dict with 'success' and 'failed' counts
        """
        self.log("=" * 60)
        self.log("Starting Sony XML to Avid Marker conversion")
        self.log(f"Input directory: {self.input_dir}")
        self.log(f"Output directory: {self.output_dir}")
        self.log(f"Recursive search: {'enabled' if self.recursive else 'disabled'}")
        if self.username:
            self.log(f"Username: {self.username}")
        else:
            self.log("Username: [using XML filename for each file]")
        self.log("=" * 60)

        # Find XML files
        xml_files = find_xml_files(self.input_dir, self.recursive, self.log)

        if not xml_files:
            self.log("No XML files found. Exiting.")
            return {"success": 0, "failed": 0}

        # Create output directory if needed
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Process each file
        stats = {"success": 0, "failed": 0}

        for i, xml_path in enumerate(xml_files, 1):
            self.log(f"\n[{i}/{len(xml_files)}] Processing: {xml_path.name}")

            result = process_single_xml(
                xml_path,
                self.output_dir,
                self.username,
                self.log,
            )

            if result:
                stats["success"] += 1
            else:
                stats["failed"] += 1

        # Final summary
        self.log("\n" + "=" * 60)
        self.log("Conversion Summary:")
        self.log(f"  Total files processed: {len(xml_files)}")
        self.log(f"  Successful: {stats['success']}")
        self.log(f"  Failed: {stats['failed']}")
        self.log("=" * 60)

        return stats
