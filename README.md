# Avid Media Composer Scripts

Tools that turn third-party metadata into files Avid Media Composer can import.

| Tool | What it does | Interface |
|---|---|---|
| [Sony XML to Avid Markers](#sony-xml-to-avid-markers) | Converts Sony camera XML shot marks into Avid marker files | CLI |
| [MediaSilo to Avid Markers](#mediasilo-to-avid-markers) | Converts a MediaSilo review-comment CSV export into an Avid marker file | CLI, GUI |
| [ALE Converter](#ale-converter) | Merges database metadata into Avid ALE files, and converts ALEs to and from spreadsheets | CLI, GUI |
| [DOCX Transcripts to Avid Scripts](#docx-transcripts-to-avid-scripts) | Converts a folder of Word transcripts into Avid script files (.avc), using [pyavc](https://github.com/lawson-tanner/pyavc) | CLI |

Each tool lives in its own folder and works on its own.

## Requirements

- Python 3.10 or newer
- Install the packages for the tool you want to use:

| Tool | Packages |
|---|---|
| Sony XML to Avid Markers | `timecode` (`Sony_XML_to_Avid_Markers/requirements.txt`) |
| MediaSilo to Avid Markers | `pandas`, plus `PyQt5` for the GUI |
| ALE Converter | `pandas`, `openpyxl`, `xlrd`, plus `PyQt5` for the GUI (`ale_converter/requirements.txt`) |
| DOCX Transcripts to Avid Scripts | `pyavc`, `python-docx` (`pyavc_scripts/requirements.txt`) |

A virtual environment is the easiest way to set this up, especially with a Homebrew-managed Python:

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
pip install -r Sony_XML_to_Avid_Markers/requirements.txt -r ale_converter/requirements.txt -r pyavc_scripts/requirements.txt
```

## Running the tools

Run each script directly by its path, e.g. `python ale_converter/ale_converter.py`. Don't run them as modules (`python -m ...`) from the repo root, because each tool loads its own `src` package from the script's folder.

## Sony XML to Avid Markers

Reads the XML sidecar files that Sony cameras write next to each clip and writes one Avid marker file per clip (`<clip>_markers.txt`).

- Only shot marks (`_ShotMark1`, `_ShotMark2`) are converted. Shot Mark 1 becomes a **Blue** marker and Shot Mark 2 becomes **Green**.
- Each marker's timecode is the clip's start timecode plus the frame offset of the mark, at the frame rate recorded in the XML.

```bash
python Sony_XML_to_Avid_Markers/sony_xml_to_avid.py /path/to/xml/folder
```

| Option | Description |
|---|---|
| `-o`, `--output DIR` | Output folder (default: same as the input folder) |
| `-u`, `--user NAME` | Username shown on the markers (default: the XML filename) |
| `-r`, `--recursive` | Also search subfolders for XML files |
| `--offset-forward SECONDS` | Shift every marker later by this many seconds |
| `--offset-backward SECONDS` | Shift every marker earlier by this many seconds |
| `-v`, `--verbose` | Show detailed logging |

You can use only one of the two offset options at a time. The script exits with status 1 if any file fails to convert.

### Unique Features

- **Reads shot marks from the XML sidecar itself.** Media Composer can show Sony shot marks as markers when the media is linked through Sony's AMA plug-in. That depends on the codec, and it doesn't help when you edit with transcoded dailies. This tool works from the XML alone.
- **Fills a gap.** General marker converters such as [EditingTools.io](https://editingtools.io/marker/) don't accept Sony camera XML, and Premiere Pro doesn't read shot marks. The closest open-source project, [sony_xml_to_ale](https://github.com/rainerfritz/sony_xml_to_ale), turns Venice XML into an ALE of clip metadata, not markers.
- **Batch processing.** It converts a whole folder at once, optionally including subfolders, and writes one marker file per clip.
- **Offsets.** It can move every marker earlier or later by a number of seconds, to make up for a sync or timecode offset.

## MediaSilo to Avid Markers

Converts a MediaSilo comment export (CSV) into a single Avid marker file.

```bash
python MediaSilo_to_Avid_Markers/MediaSilo_to_Avid.py input.csv output.txt
```

Or use the GUI:

```bash
python MediaSilo_to_Avid_Markers/MediaSilo_to_Avid_GUI.py
```

- The CSV must have a header row with a `Timecode` column, and timecodes in `HH:MM:SS:FF` format. `Name` and `Comment` columns are optional. MediaSilo has a plain CSV export with no header row and timecodes without frames (see `Sample Files/MediaSilo_CSV.csv`), and this tool doesn't support it yet.
- Comments that share a timecode are combined into one marker: the comments are joined with ` | ` and the reviewer names with `, `.
- All markers are **Red** on track V1. Colons in comments are replaced with `--`, and line breaks and tabs become spaces so each comment fits on one line.
- The CLI writes a log to `mediasilo_conversion.log` in the current folder.

Sample exports are in `MediaSilo_to_Avid_Markers/Sample Files/`.

### Unique Features

- **Built for MediaSilo's export.** Frame.io and Screenlight can export Avid marker files themselves. MediaSilo doesn't appear to offer that. General converters such as [EditingTools.io](https://editingtools.io/marker/) have no MediaSilo preset, so you have to map the columns yourself. This tool reads MediaSilo's own column names and drops the columns Avid doesn't need.
- **Prevents overlapping markers.** Media Composer can refuse to import a marker file when markers overlap. When several reviewers comment at the same timecode, the tool combines their comments into one marker and lists every reviewer.
- **Output Avid accepts.** Tabs and line breaks become spaces, and colons are replaced, so each comment fits on one valid marker line.
- **Runs locally with no limits.** Client feedback never leaves your machine. There are no limits on file size or marker count, unlike the free tiers of web converters.

## ALE Converter

Works with Avid Log Exchange (ALE) files. It has three commands, and the GUI covers the same three.

```bash
python ale_converter/ale-converter-gui.py
```

### `merge`: add database metadata to an ALE

Matches each clip in an Avid ALE to a row in a database export (CSV or Excel, e.g. from Airtable) and writes a new ALE with the database columns added.

```bash
python ale_converter/ale_converter.py merge --ale AVID.ale --db DATABASE.csv --output MERGED.ale
```

How matching works:

- The database's `NUMBER` column holds each record's ID.
- The clip's ID comes from its `Name`. The name is split on `_` and the second part is used by default. For example, `A001_ARC1234_v2` gives `ARC1234`.
- If no clips match, the converter tries the other parts of the name automatically. Use `--id-position N` to pick the part yourself (counting from 0).
- If the database has the same ID more than once, the first row is used and a warning is printed.

| Option | Description |
|---|---|
| `--output FILE` | Output ALE path |
| `--id-position N` | Which `_`-separated part of the clip name holds the ID (0-based) |
| `--custom-columns FILE` | JSON file listing the columns to drop and rename (see below) |
| `--fps FPS` | Override the frame rate (default: keep the source ALE's) |
| `-v`, `--verbose` | Show detailed logging |

Text is cleaned before it goes into the ALE. Curly quotes are straightened, line breaks become ` // `, and fields are cut to 253 characters.

#### Choosing output columns

[`ale_converter/custom_columns.json`](ale_converter/custom_columns.json) sets which database columns are left out (`columns_to_drop`) and which are renamed (`columns_to_rename`). Copy it, edit it, and pass it with `--custom-columns`. Keys that start with `_` are comments and are ignored.

After merging, the clip name column is called `Name_x`. Rename it with that name, e.g. `"Name_x": "Clip Name"`.

### `export`: ALE to spreadsheet

```bash
python ale_converter/ale_converter.py export --ale AVID.ale --output CLIPS.csv --format csv
```

- `--format csv` writes the clip data to the output file and the ALE header to a second file ending in `_headers.csv`.
- `--format excel` writes one `.xlsx` with `ALE_Data` and `ALE_Headers` sheets.

### `convert`: spreadsheet to ALE

```bash
python ale_converter/ale_converter.py convert --spreadsheet CLIPS.csv --fps 23.976 --output CLIPS.ale
```

- `--fps` is required. Accepted values: 23.976, 24, 25, 29.97, 30, 59.94, 60, 119.88, 120.
- `--template FILE.ale` copies the header (video format, audio format, custom fields) from an existing ALE. The frame rate still comes from `--fps`.
- Reads `.csv`, `.xlsx`, `.xlsm`, and legacy `.xls` files.
- Blank rows are skipped.
- Cells that contain only `NA`, `N/A`, `None`, or `null` in a CSV are read as empty.

### Unique Features

- **Matches clips to records by ID.** Avid's own Shot Log merge matches clips by timecode and can blank fields that already have values. Web tools such as the [EditingTools.io ALE Converter](https://editingtools.io/ale/) only merge field-recorder scene and take data by timecode. `merge` instead takes an archive ID from each clip name and matches it to a database record, which suits archival and documentary work where clips are logged by ID.
- **Tries other ID positions automatically.** If no clips match, it tries the other parts of the clip name before giving up.
- **Repeatable column setup.** A JSON file sets which columns to drop and rename. The same database export comes out the same way on every run, with no manual cleanup.
- **Text cleaning for Avid.** It fixes the characters that make Avid reject an ALE or show bad data, such as curly quotes, line breaks, tabs, and fields that are too long.
- **Safe round trips.** Exporting an ALE to CSV and converting it back keeps every column and value. You can edit metadata in a spreadsheet and send it back to Avid without losing data.
- **Runs locally.** Database exports and clip metadata never leave your machine. There are no conversion limits, and it can be scripted into a larger pipeline.

## DOCX Transcripts to Avid Scripts

Converts every Word transcript (`.docx`) in a folder into an Avid Media Composer script file (`.avc`). The .avc files are written by [pyavc](https://github.com/lawson-tanner/pyavc) by Lawson Tanner. See [Credits and licensing](#credits-and-licensing).

```bash
python pyavc_scripts/docx_to_avid_script.py /path/to/transcripts
```

The scripts are saved to an `avid_scripts` subfolder inside the input folder, one `.avc` per transcript with the same name.

- Paragraphs and table rows are read in document order. Each table row becomes one line, with its cells separated by spaces.
- Curly quotes, dashes, ellipses, and non-breaking spaces are turned into plain ASCII by default.
- Lines longer than `--text-width` characters are split into several lines.
- Word lock files (`~$...`) are ignored. Empty documents are skipped with a warning.
- The script exits with status 1 if any file fails to convert.

| Option | Description |
|---|---|
| `-o`, `--output DIR` | Output folder (default: `avid_scripts` inside the input folder) |
| `-r`, `--recursive` | Also convert transcripts in subfolders, keeping the folder structure |
| `--if-exists skip\|overwrite\|rename` | What to do when the .avc already exists (default: `skip`). `rename` writes `Name(1).avc` |
| `--keep-unicode` | Keep typographic punctuation instead of converting it to ASCII |
| `--no-tables` | Ignore text in Word tables |
| `-v`, `--verbose` | Show detailed logging |

Script formatting options match Media Composer's Script settings, and you can change all of them later in Avid:

| Option | Default |
|---|---|
| `-t`, `--text-width N`: characters per line | 80 |
| `-f`, `--font-size PX` | 12 |
| `--font NAME` | Open Sans |
| `--white-bg` / `--no-white-bg` | off (uses Avid's setting) |
| `--row-colors` / `--no-row-colors` | on |
| `--left-margin PX` | 40 |
| `--text-width-px PX` (128–5120, display only) | 512 |
| `--frames` / `--no-frames`: slate thumbnail | on |
| `--interpolate-position` / `--no-interpolate-position` | off |
| `--all-takes` / `--no-all-takes` | on |
| `--line-numbers` / `--no-line-numbers` | on |
| `--word-wrap` / `--no-word-wrap` | on |
| `--hold-slates` / `--no-hold-slates` | off |
| `--take-color N` (1–22, [palette](https://github.com/lawson-tanner/pyavc#take_color-palette)) | 1 |

### Unique Features

- **Whole folders at once.** pyavc's own command converts one file at a time. This tool converts a folder, optionally with its subfolders, and reports a summary.
- **Reads transcript tables.** Some transcription services put timecode, speaker, and dialogue in Word tables. This tool includes table text, where pyavc's DOCX reader only reads paragraphs.
- **Safe re-runs.** Existing scripts are skipped by default, or overwritten or numbered on request. Each file is built in a temporary folder and moved into place, so a failed conversion never leaves a partial file.
- **Checked options.** Formatting values are checked against pyavc's limits before anything is converted.

### Credits and licensing

The .avc files are written by **[pyavc](https://github.com/lawson-tanner/pyavc)**, created by **Lawson Tanner** and licensed under the GNU General Public License v3.0. pyavc is installed from PyPI as a dependency, not bundled. pyavc is not affiliated with Avid, and neither is this project.

Because this tool is built on pyavc, the `pyavc_scripts/` folder is released under **GPL-3.0** ([`pyavc_scripts/LICENSE`](pyavc_scripts/LICENSE)). See [`pyavc_scripts/NOTICE.md`](pyavc_scripts/NOTICE.md) for full credits.

## Avid marker file format

Both marker tools write tab-separated text that Media Composer imports from the Markers window (**Import Markers**). Each line is one marker:

```
<user>  <HH:MM:SS:FF>  V1  <color>  <comment>  1  <empty>  <color>
```

Usernames are lowercase with spaces and commas removed.
