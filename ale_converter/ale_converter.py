"""
ALE Converter V2

This script converts and merges AVID ALE files with metadata from an AIRTABLE CSV export.
It extracts archival IDs from clip names, matches them with database records,
and creates a new ALE file with the merged metadata.

Usage:
    python ale_converter.py --ale AVID.ale --db AIRTABLE.csv [--output OUTPUT.ale]
"""

import os
import pandas as pd
import re
import argparse
import sys
import json
from pathlib import Path

class ALEConverter:
    """A class to convert and merge ALE files with metadata from a CSV database."""
    
    def __init__(self, ale_path, db_path, output_path=None, verbose=False):
        """Initialize the converter with file paths."""
        self.ale_path = Path(ale_path)
        self.db_path = Path(db_path)
        self.output_path = Path(output_path) if output_path else Path("AVID_WITH_ARC_DATA.ale")
        self.verbose = verbose
        
        # Data containers
        self.db = None
        self.ale = None
        self.ale_h = None
        self.df_db = None
        self.df_ale = None
        self.df_ale_db = None
        self.df_ale_db_exp = None
        self.ale_old = None
        self.ale_old_read = None
        self.old_h = None
        self.old_h1 = None
        self.old_h2 = None
        self.new_ale = None
        
        # Column mappings
        self.column_mappings = {}

    def create_new_ale(self):
        """Create a new ALE file with original metadata and merged data"""
        print("Creating new ALE file")
        
        # Get the header and structure from the original ALE file
        self.get_original_ale_metadata()
        
        # Convert merged data to tab-separated format
        csv = self.df_ale_db_exp.to_csv(sep='\t', index=False)
        
        # Extract column names and data rows
        csv_header, csv_data = csv.split('\n', 1)
        
        # Format the column section using our new columns, preserving the original format
        new_column_section = self.column_section.split("\n", 1)[0]  # Get the "Column" line
        new_column_section += "\n" + csv_header
        
        # Clean up formatting issues in data
        csv_data = csv_data.replace('\"\"\"', '')  # Remove triple double quotes
        csv_data = csv_data.replace('\"\"', '\"')  # Remove double double quotes
        csv_data = csv_data.replace('\t\"', '\t')  # Remove leading double quotes
        csv_data = csv_data.replace('\"\t', '\t')  # Remove trailing double quotes
        
        # Assemble the new ALE file, preserving the original structure
        self.new_ale = self.header_section + new_column_section + self.data_marker + csv_data
        
        # For debugging, print first few lines of new ALE
        if self.verbose:
            debug_lines = self.new_ale.split('\n')[:20]
            self.debug_print(f"First few lines of new ALE file:")
            for line in debug_lines:
                self.debug_print(line)

    def export_ale_to_spreadsheet(self, ale_path, output_path=None, format='csv'):
        """
        Export an ALE file to CSV or Excel format
        
        Args:
            ale_path (str or Path): Path to the ALE file
            output_path (str or Path, optional): Path for the output file. If None, uses the same name as ALE
            format (str): Output format - 'csv' or 'excel'
            
        Returns:
            str: Path to the created output file
        """
        print(f"Exporting ALE file {ale_path} to {format.upper()} format")
        
        ale_path = Path(ale_path)
        
        # Determine output path if not specified
        if output_path is None:
            if format.lower() == 'csv':
                output_path = ale_path.with_suffix('.csv')
            else:
                output_path = ale_path.with_suffix('.xlsx')
        else:
            output_path = Path(output_path)
        
        try:
            # Read ALE file
            # First, find where the column headers start
            header_line_index = None
            data_line_index = None
            
            with open(ale_path, 'r') as f:
                lines = f.readlines()
                for i, line in enumerate(lines):
                    if line.strip() == 'Column':
                        header_line_index = i + 1
                    if line.strip() == 'Data':
                        data_line_index = i + 1
                        break
            
            if header_line_index is None or data_line_index is None:
                raise ValueError("Could not find Column or Data markers in ALE file")
                
            # Get the column headers
            ale_headers = ''.join(lines[header_line_index:data_line_index-1]).strip()
            ale_columns = [col.strip() for col in ale_headers.split('\t') if col.strip()]
            
            # Read the ALE data
            df_ale = pd.read_csv(
                ale_path, 
                sep='\t', 
                lineterminator='\r', 
                skiprows=data_line_index, 
                names=ale_columns,
                dtype=str
            )
            
            # Handle any parsing issues
            df_ale.fillna('', inplace=True)
            
            # Remove the null row if it exists (last row with all 'null' values)
            if 'null' in str(df_ale.iloc[-1].values):
                df_ale = df_ale.iloc[:-1]
            
            print(f"Read {len(df_ale)} clips from ALE file")
            
            # Export to the specified format
            if format.lower() == 'csv':
                df_ale.to_csv(output_path, index=False)
                print(f"Exported to CSV: {output_path}")
            else:
                # Check if pandas has Excel support
                try:
                    import openpyxl
                    df_ale.to_excel(output_path, index=False, engine='openpyxl')
                    print(f"Exported to Excel: {output_path}")
                except ImportError:
                    print("Excel export requires openpyxl. Install with: pip install openpyxl")
                    print("Falling back to CSV export")
                    output_path = output_path.with_suffix('.csv')
                    df_ale.to_csv(output_path, index=False)
                    print(f"Exported to CSV: {output_path}")
            
            return str(output_path)
            
        except Exception as e:
            print(f"Error exporting ALE to {format.upper()}: {e}")
            return None

    def debug_print(self, *args, **kwargs):
        """Print debug information if verbose mode is enabled"""
        if self.verbose:
            print("[DEBUG]", *args, **kwargs)
    
    def read_files(self):
        """Read and parse input files"""
        print(f"Reading database from {self.db_path}")
        try:
            # Check file extension to determine how to read it
            file_ext = self.db_path.suffix.lower()
            
            if file_ext in ['.xlsx', '.xls', '.xlsm']:
                # Excel file detected
                self.db = self.read_excel_database(self.db_path)
            else:
                # Default to CSV
                self.db = pd.read_csv(self.db_path, dtype=str)
                
        except FileNotFoundError:
            print(f"Error: Database file '{self.db_path}' not found.")
            sys.exit(1)
        except Exception as e:
            print(f"Error reading database file: {e}")
            sys.exit(1)
            
        print(f"Reading ALE file from {self.ale_path}")
        try:
            # Get ALE header data from line 8
            self.ale_h = pd.read_csv(
                self.ale_path, 
                sep='\t', 
                lineterminator='\r', 
                skiprows=range(0, 7), 
                nrows=1
            )
            
            # Get ALE body data from line 11 and onward
            self.ale = pd.read_csv(
                self.ale_path, 
                sep='\t', 
                lineterminator='\r', 
                skiprows=range(0, 10), 
                header=None
            )
            
            # Use header row to name columns
            self.ale.columns = self.ale_h.columns
            
        except FileNotFoundError:
            print(f"Error: ALE file '{self.ale_path}' not found.")
            sys.exit(1)
        except Exception as e:
            print(f"Error reading ALE file: {e}")
            sys.exit(1)
            
        # Convert to dataframes for manipulation
        self.df_db = pd.DataFrame(self.db)
        self.df_ale = pd.DataFrame(self.ale)
        
        print(f"Successfully read files. Database has {len(self.df_db)} rows, ALE has {len(self.df_ale)} rows.")
        
        # Print column names for debugging
        self.debug_print("Database columns:", self.df_db.columns.tolist())
        self.debug_print("ALE columns:", self.df_ale.columns.tolist())
        
        # Print first few rows of data for debugging
        if self.verbose and len(self.df_db) > 0:
            self.debug_print("First database row:")
            for col in self.df_db.columns[:5]:  # Just show first 5 columns
                value = self.df_db.iloc[0][col]
                self.debug_print(f"  {col}: {value}")
                
        if self.verbose and len(self.df_ale) > 0:
            self.debug_print("First ALE row:")
            for col in self.df_ale.columns[:5]:  # Just show first 5 columns
                value = self.df_ale.iloc[0][col]
                self.debug_print(f"  {col}: {value}")

    def read_excel_database(self, path):
        """
        Read an Excel file with support for sheet selection
        
        Args:
            path (Path): Path to the Excel file
            
        Returns:
            pandas.DataFrame: Data from the selected sheet
        """
        import pandas as pd
        
        try:
            # If a specific sheet was specified in command line arguments
            if hasattr(self, 'sheet_name') and self.sheet_name is not None:
                sheet_name = self.sheet_name
                print(f"Reading sheet '{sheet_name}' from Excel file")
                return pd.read_excel(path, sheet_name=sheet_name, dtype=str)
            
            # If we should list all sheets
            if hasattr(self, 'list_sheets') and self.list_sheets:
                # Read the Excel file to get sheet names only
                import openpyxl
                wb = openpyxl.load_workbook(path, read_only=True)
                sheet_names = wb.sheetnames
                wb.close()
                
                print("Available sheets in Excel file:")
                for i, name in enumerate(sheet_names, 1):
                    print(f"  {i}: {name}")
                
                print("\nUse --sheet <name> to select a specific sheet")
                sys.exit(0)
            
            # If not specified, try to use the first sheet
            try:
                # First check if there are multiple sheets
                xl = pd.ExcelFile(path)
                sheet_names = xl.sheet_names
                
                if len(sheet_names) > 1:
                    print(f"Found {len(sheet_names)} sheets in Excel file.")
                    print(f"Using first sheet: '{sheet_names[0]}'")
                    print(f"Use --list-sheets to see all sheets or --sheet <name> to select a specific sheet.")
                
                # Read the first sheet
                return pd.read_excel(path, sheet_name=0, dtype=str)
                
            except Exception as e:
                print(f"Error reading Excel file: {e}")
                sys.exit(1)
                
        except ImportError:
            print("Error: Excel support requires openpyxl and pandas")
            print("Install them with: pip install openpyxl pandas")
            sys.exit(1)

    def validate_excel_sheet(self, excel_path, sheet_name):
        """
        Validate that the specified sheet exists in the Excel file
        
        Args:
            excel_path (Path): Path to the Excel file
            sheet_name (str): Name or index of the sheet to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            # Get all sheet names
            import pandas as pd
            xl = pd.ExcelFile(excel_path)
            sheet_names = xl.sheet_names
            
            # Check if sheet exists by name
            if sheet_name in sheet_names:
                return True
                
            # Check if sheet exists by index
            try:
                index = int(sheet_name)
                if 0 <= index < len(sheet_names):
                    # Update sheet_name to be the actual name (not index)
                    self.sheet_name = sheet_names[index]
                    return True
            except ValueError:
                # Not an integer index
                pass
                
            # Sheet not found
            print(f"Error: Sheet '{sheet_name}' not found in {excel_path}")
            print(f"Available sheets: {', '.join(sheet_names)}")
            return False
        
        except Exception as e:
            print(f"Error validating Excel sheet: {e}")
            return False

    def clean_database(self):
        """Clean and normalize database data"""
        print("Cleaning database data")
        
        # Make empty cells show up as empty instead of 'NaN'
        self.df_db.fillna('', inplace=True)
        
        # Replace illegal AVID characters
        char_replacements = {
            '\n': ' // ',
            '\\n': ' // ',
            '\\\n': ' // ',
            '\t': ' ',
            '\u000D': ' // ',  # Carriage return
            '\u2018': '\u0027',  # Left curly apostrophe to regular apostrophe
            '\u2019': '\u0027',  # Right curly apostrophe to regular apostrophe
            '\u201C': '\u0022',  # Left curly double quotes to regular quotes
            '\u201D': '\u0022',  # Right curly double quotes to regular quotes
            '\u2013': '\u002D',  # Endash to hyphen
            '\u2026': '...',    # Ellipsis to three dots
            '・・・': '...',     # Weird spaced out ellipsis to three dots
            '\u00BE': '3/4',    # ¾ to 3/4
            '\u00BD': '1/2',    # ½ to 1/2
            '\u00BC': '1/4',    # ¼ to 1/4
            '\u00E9': 'e',      # é to e
            '🙏': '',           # Remove 'Thank You' emoji
        }
        
        for old, new in char_replacements.items():
            self.df_db = self.df_db.replace(old, new, regex=True)
        
        # Trim columns to 254 characters for AVID
        self.df_db = self.df_db.astype(str).apply(lambda x: x.str.slice(0, 253))
    
    def clean_ale(self):
        """Clean and normalize ALE data"""
        print("Cleaning ALE data")
        
        # Drop blank columns
        self.df_ale = self.df_ale[self.df_ale.columns.drop(list(self.df_ale.filter(regex='Unnamed')))]
        
        # Replace empty cells with empty strings
        self.df_ale.fillna('', inplace=True)
        
        # Remove newlines
        self.df_ale = self.df_ale.replace('\n', '', regex=True)
    
    def extract_db_ids(self):
        """Extract archival IDs from database"""
        print("Extracting archival IDs from database")
        
        # Check if NUMBER column exists
        if 'NUMBER' not in self.df_db.columns:
            print("Warning: 'NUMBER' column not found in database. Available columns:")
            print(", ".join(self.df_db.columns))
            print("Using first column as ID column")
            id_column = self.df_db.columns[0]
        else:
            id_column = 'NUMBER'
        
        # Use NUMBER column as ARC_ID
        self.df_db["ARC_ID"] = self.df_db[id_column].astype(str)
        
        # Print some sample database IDs for debugging
        sample_ids = self.df_db['ARC_ID'].iloc[:3].tolist() if len(self.df_db) >= 3 else self.df_db['ARC_ID'].tolist()
        print(f"Sample database IDs: {sample_ids}")
        
        # Check if IDs look valid
        if all(not id or id.isspace() for id in sample_ids):
            print("Warning: Database IDs appear to be empty. Check the NUMBER column in your database.")
    
    def extract_ale_ids(self):
        """Extract archival IDs from ALE clip names"""
        print("Extracting archival IDs from ALE clip names")
        
        # Ensure Name column isn't NaN
        self.df_ale["Name"].fillna('', inplace=True)
        
        # Print some sample names for debugging
        sample_names = self.df_ale['Name'].iloc[:3].tolist()
        print(f"Sample clip names: {sample_names}")
        
        # Split the name by underscore
        id_prep = pd.DataFrame(
            self.df_ale["Name"].str.split('_', n=2, expand=True).values,
            columns=['col1', 'col2', 'col3']
        )
        
        # Use the second component as the ARC_ID
        arc_id = id_prep['col2']
        self.df_ale.insert(0, 'ARC_ID', arc_id)
        
        # Print some sample IDs for debugging
        sample_ids = self.df_ale['ARC_ID'].iloc[:3].tolist()
        print(f"Sample extracted IDs: {sample_ids}")
        
        # Print sample of name to ID mapping
        self.debug_print("Sample name to ID mapping:")
        for i in range(min(3, len(self.df_ale))):
            name = self.df_ale['Name'].iloc[i]
            id_val = self.df_ale['ARC_ID'].iloc[i]
            self.debug_print(f"  {name} -> {id_val}")
    
    def merge_data(self):
        """Merge ALE data with database data based on archival IDs"""
        print("Merging ALE with database")
        
        # Select columns to merge from ALE
        selected_ale_columns = ['ARC_ID', 'Name', 'Start', 'End', 'Tape', 'Source File']
        selected_ale_columns = [col for col in selected_ale_columns if col in self.df_ale.columns]
        
        # Print IDs for debugging
        print(f"Number of unique IDs in ALE: {self.df_ale['ARC_ID'].nunique()}")
        print(f"Number of unique IDs in database: {self.df_db['ARC_ID'].nunique()}")
        
        # Find overlap between ALE and database IDs
        ale_ids = set(self.df_ale['ARC_ID'].dropna().unique())
        db_ids = set(self.df_db['ARC_ID'].dropna().unique())
        common_ids = ale_ids.intersection(db_ids)
        print(f"Number of matching IDs: {len(common_ids)}")
        print(f"Sample matching IDs: {list(common_ids)[:5] if common_ids else 'No matching IDs found'}")
        
        # If no matching IDs, try alternative ID matching strategies
        if not common_ids:
            print("Warning: No matching IDs found. Trying alternative ID extraction...")
            self.try_alternative_id_extraction()
            
            # Check again for matching IDs
            ale_ids = set(self.df_ale['ARC_ID'].dropna().unique())
            db_ids = set(self.df_db['ARC_ID'].dropna().unique())
            common_ids = ale_ids.intersection(db_ids)
            print(f"After alternative extraction - Number of matching IDs: {len(common_ids)}")
            print(f"Sample matching IDs: {list(common_ids)[:5] if common_ids else 'Still no matching IDs found'}")
        
        # Merge on ARC_ID
        self.df_ale_db = self.df_ale[selected_ale_columns].merge(
            self.df_db, how='left', on=['ARC_ID']
        )
        
        # Check if merge was successful
        print(f"Merged data has {len(self.df_ale_db)} rows")
        
        # Check for specific columns that should be present
        expected_columns = ['DATE', 'BRIEF DESCRIPTION', 'LONG DESCRIPTION']
        for col in expected_columns:
            if col in self.df_ale_db.columns:
                null_count = self.df_ale_db[col].isna().sum()
                print(f"Column '{col}' has {null_count} null values out of {len(self.df_ale_db)} rows")
            else:
                print(f"Warning: Expected column '{col}' not found in merged data")
    
    def try_alternative_id_extraction(self):
        """Try alternative methods to extract IDs from clip names"""
        print("Trying alternative ID extraction methods")
        
        # Try different parts of the name
        for part_index in range(0, 3):
            # Skip if we already tried this index
            if part_index == 1:  # We already tried part 1 (index 1)
                continue
                
            print(f"Trying name part {part_index + 1} as ID")
            
            # Split the name by underscore
            id_prep = pd.DataFrame(
                self.df_ale["Name"].str.split('_', n=3, expand=True).values,
                columns=['col0', 'col1', 'col2', 'col3']
            )
            
            # Use the specified component as the ARC_ID
            if f'col{part_index}' in id_prep.columns:
                arc_id = id_prep[f'col{part_index}']
                self.df_ale['ARC_ID'] = arc_id
                
                # Print some sample IDs for debugging
                sample_ids = self.df_ale['ARC_ID'].iloc[:3].tolist()
                print(f"Sample extracted IDs using part {part_index + 1}: {sample_ids}")
                
                # Check for overlap
                ale_ids = set(self.df_ale['ARC_ID'].dropna().unique())
                db_ids = set(self.df_db['ARC_ID'].dropna().unique())
                common_ids = ale_ids.intersection(db_ids)
                
                if common_ids:
                    print(f"Found {len(common_ids)} matching IDs using part {part_index + 1}")
                    return
        
        # If we still don't have matches, try using the entire name as ID
        print("Trying full name as ID")
        self.df_ale['ARC_ID'] = self.df_ale['Name']
        
        # Check for overlap
        ale_ids = set(self.df_ale['ARC_ID'].dropna().unique())
        db_ids = set(self.df_db['ARC_ID'].dropna().unique())
        common_ids = ale_ids.intersection(db_ids)
        
        if common_ids:
            print(f"Found {len(common_ids)} matching IDs using full name")
            return
            
        print("Could not find a matching ID strategy. Metadata may be missing in output.")
    
    def prepare_ale_columns(self, columns_to_drop=None, columns_to_rename=None):
        """Prepare ALE columns for export with custom drop and rename options"""
        print("Preparing ALE columns for export with custom configuration")
        
        # If no custom configuration is provided, use default
        if columns_to_drop is None:
            # Base columns to drop - DO NOT include 'ARC_ID' here
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
            
            # Combine into a list of columns to drop
            columns_to_drop = base_columns.copy()
            for pattern in regex_patterns:
                regex_matches = list(self.df_db.filter(regex=pattern).columns)
                columns_to_drop.extend(regex_matches)
        
        # If no custom rename is provided, use default
        if columns_to_rename is None:
            columns_to_rename = {
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
        
        # Verbose logging of configuration
        print("Columns to drop:", columns_to_drop)
        print("Columns to rename:", columns_to_rename)
        
        # Prepare the dataframe
        # First, drop specified columns
        df_to_export = self.df_ale_db.copy()
        
        # Drop columns that exist in the dataframe
        columns_to_drop_actual = [col for col in columns_to_drop if col in df_to_export.columns]
        df_to_export = df_to_export.drop(columns=columns_to_drop_actual, errors='ignore')
        
        # Rename columns
        # Only rename columns that actually exist in the dataframe
        rename_dict = {
            old_col: new_col 
            for old_col, new_col in columns_to_rename.items() 
            if old_col in df_to_export.columns
        }
        df_to_export = df_to_export.rename(columns=rename_dict)
        
        # Store the modified dataframe
        self.df_ale_db_exp = df_to_export
        
        # Add a "null" row at the bottom (required for ALE format)
        self.df_ale_db_exp = self.df_ale_db_exp._append(
            pd.Series("null", index=self.df_ale_db_exp.columns), 
            ignore_index=True
        )
        
        # Verbose logging of final columns
        print("Final columns in output:")
        for col in self.df_ale_db_exp.columns:
            print(f"  {col}")
        
        return self.df_ale_db_exp
    
    def get_original_ale_metadata(self):
        """Extract all metadata from the original ALE file"""
        print("Extracting original ALE metadata")
        
        with open(self.ale_path, 'r') as f:
            self.ale_old_read = f.read()
        
        # Find the start of Column section
        column_start_index = self.ale_old_read.find("\nColumn")
        if column_start_index == -1:
            print("Warning: Could not find 'Column' section in ALE file")
            column_start_index = self.ale_old_read.find("\nData")
        
        # Extract the header (everything before Column section)
        self.header_section = self.ale_old_read[:column_start_index]
        
        # Extract Column line and the following section until Data
        data_start_index = self.ale_old_read.find("\nData")
        if data_start_index == -1:
            print("Warning: Could not find 'Data' section in ALE file")
            self.column_section = self.ale_old_read[column_start_index:]
            self.data_marker = "\nData\n"
        else:
            self.column_section = self.ale_old_read[column_start_index:data_start_index]
            # Get the Data marker line (could include formatting)
            data_end_line_index = self.ale_old_read.find("\n", data_start_index + 1)
            if data_end_line_index == -1:
                self.data_marker = "\nData\n"
            else:
                next_line_index = self.ale_old_read.find("\n", data_end_line_index + 1)
                if next_line_index == -1:
                    self.data_marker = self.ale_old_read[data_start_index:data_end_line_index] + "\n"
                else:
                    self.data_marker = self.ale_old_read[data_start_index:next_line_index]
        
        self.debug_print(f"Header section: {self.header_section}")
        self.debug_print(f"Column section: {self.column_section}")
        self.debug_print(f"Data marker: {self.data_marker}")
    
    def create_new_ale(self):
        """Create a new ALE file with original metadata and merged data"""
        print("Creating new ALE file")
        
        # Get the header and structure from the original ALE file
        self.get_original_ale_metadata()
        
        # Convert merged data to tab-separated format
        csv = self.df_ale_db_exp.to_csv(sep='\t', index=False)
        
        # Extract column names and data rows
        csv_header, csv_data = csv.split('\n', 1)
        
        # Format the column section using our new columns, preserving the original format
        new_column_section = self.column_section.split("\n", 1)[0]  # Get the "Column" line
        new_column_section += "\n" + csv_header
        
        # Clean up formatting issues in data
        csv_data = csv_data.replace('\"\"\"', '')  # Remove triple double quotes
        csv_data = csv_data.replace('\"\"', '\"')  # Remove double double quotes
        csv_data = csv_data.replace('\t\"', '\t')  # Remove leading double quotes
        csv_data = csv_data.replace('\"\t', '\t')  # Remove trailing double quotes
        
        # Assemble the new ALE file, preserving the original structure
        self.new_ale = self.header_section + new_column_section + self.data_marker + csv_data
        
        # For debugging, print first few lines of new ALE
        if self.verbose:
            debug_lines = self.new_ale.split('\n')[:20]
            self.debug_print(f"First few lines of new ALE file:")
            for line in debug_lines:
                self.debug_print(line)
    
    def write_output(self):
        """Write the new ALE file to disk"""
        print(f"Writing output to {self.output_path}")
        
        try:
            with open(self.output_path, 'w') as f:
                f.write(self.new_ale)
            print(f"Successfully created {self.output_path}")
            return str(self.output_path)  # Make sure to return the path
        except Exception as e:
            print(f"Error writing output file: {e}")
            sys.exit(1)
    
    def print_column_info(self):
        """Print detailed information about columns in both files"""
        print("\n===== ALE COLUMNS =====")
        for i, col in enumerate(self.df_ale.columns):
            print(f"{i}: {col}")
            if i < 3 and len(self.df_ale) > 0:  # Show sample values from first row
                print(f"   Sample: {self.df_ale[col].iloc[0]}")
        
        print("\n===== DATABASE COLUMNS =====")
        for i, col in enumerate(self.df_db.columns):
            print(f"{i}: {col}")
            if i < 3 and len(self.df_db) > 0:  # Show sample values from first row
                print(f"   Sample: {self.df_db[col].iloc[0]}")
        
        if hasattr(self, 'df_ale_db') and self.df_ale_db is not None:
            print("\n===== MERGED DATA COLUMNS =====")
            for i, col in enumerate(self.df_ale_db.columns):
                print(f"{i}: {col}")
                if i < 3 and len(self.df_ale_db) > 0:  # Show sample values from first row
                    print(f"   Sample: {self.df_ale_db[col].iloc[0]}")
    
    def visualize_mapping(self):
        """Visualize the column mappings between CSV and ALE files"""
        if not self.column_mappings:
            print("No column mappings available. Run convert() first or use --mapping with --preview.")
            return
            
        print("\n===== COLUMN MAPPING VISUALIZATION =====")
        print(f"{'DATABASE COLUMN':<30} | {'ALE OUTPUT COLUMN':<30} | {'SAMPLE VALUE':<30}")
        print("-" * 95)
        
        # Sort mappings by destination column name
        sorted_mappings = sorted(
            self.column_mappings.items(), 
            key=lambda x: (x[1] is None, x[1] if x[1] else "")
        )
        
        for db_col, ale_col in sorted_mappings:
            # Get a sample value from the database
            sample_val = ""
            if len(self.df_db) > 0 and db_col in self.df_db.columns:
                sample_val = str(self.df_db[db_col].iloc[0])
                if len(sample_val) > 30:
                    sample_val = sample_val[:27] + "..."
            
            # Display the mapping
            if ale_col:
                print(f"{db_col:<30} | {ale_col:<30} | {sample_val:<30}")
            else:
                print(f"{db_col:<30} | {'[DROPPED]':<30} | {sample_val:<30}")
        
        print("\n===== ALE OUTPUT COLUMNS (FINAL ORDER) =====")
        if hasattr(self, 'df_ale_db_exp') and self.df_ale_db_exp is not None:
            ale_columns = self.df_ale_db_exp.columns.tolist()
            db_columns = self.df_db.columns.tolist()
            
            for i, col in enumerate(ale_columns):
                # Determine if this is from the database or original ALE
                if col in [self.column_mappings.get(db_col) for db_col in db_columns]:
                    source = "DATABASE"
                    
                    # Find the original database column
                    orig_col = next((db_col for db_col, ale_col in self.column_mappings.items() 
                                    if ale_col == col), None)
                else:
                    source = "ORIGINAL ALE"
                    orig_col = col
                
                # Get a sample value
                sample_val = ""
                if len(self.df_ale_db_exp) > 1:  # Skip the null row
                    sample_val = str(self.df_ale_db_exp[col].iloc[0])
                    if len(sample_val) > 30:
                        sample_val = sample_val[:27] + "..."
                
                # Show column info
                if orig_col and orig_col != col:
                    print(f"{i+1}: {col:<25} (from {source}: {orig_col}) = {sample_val}")
                else:
                    print(f"{i+1}: {col:<25} (from {source}) = {sample_val}")
    
    def set_manual_id_extraction(self, position):
        """
        Manually set which component of the filename (split by underscores) to use as ID
        
        Args:
            position (int): Zero-based position in the filename when split by underscores
        """
        print(f"Manually setting ID extraction to use component {position} from filename")
        
        # Ensure Name column isn't NaN
        self.df_ale["Name"].fillna('', inplace=True)
        
        # Split the name by underscore
        id_prep = pd.DataFrame(
            self.df_ale["Name"].str.split('_', n=position+1, expand=True).values,
            columns=[f'col{i}' for i in range(position+2)]
        )
        
        # Use the specified component as the ARC_ID
        if f'col{position}' in id_prep.columns:
            arc_id = id_prep[f'col{position}']
            # Replace the ARC_ID column if it exists
            if 'ARC_ID' in self.df_ale.columns:
                self.df_ale['ARC_ID'] = arc_id
            else:
                self.df_ale.insert(0, 'ARC_ID', arc_id)
            
            # Print some sample IDs for debugging
            sample_ids = self.df_ale['ARC_ID'].iloc[:3].tolist()
            print(f"Sample extracted IDs using position {position}: {sample_ids}")
        else:
            print(f"Error: Position {position} is out of range for most filenames")
    
    def convert(self):
        """Run the full conversion process"""
        print(f"Starting conversion of {self.ale_path} with {self.db_path}")
        
        self.read_files()
        self.clean_database()
        self.clean_ale()
        self.extract_db_ids()
        self.extract_ale_ids()
        self.merge_data()
        self.prepare_ale_columns()
        self.create_new_ale()
        self.write_output()
        
        return str(self.output_path)

    @staticmethod
    def convert_spreadsheet_to_ale(spreadsheet_path, output_path=None, template_ale_path=None):
        """
        Convert a CSV or Excel file to ALE format
        
        Args:
            spreadsheet_path (str or Path): Path to the CSV or Excel file
            output_path (str or Path, optional): Path for the output ALE file
            template_ale_path (str or Path, optional): Path to a template ALE file for header structure
            
        Returns:
            str: Path to the created ALE file
        """
        print(f"Converting spreadsheet {spreadsheet_path} to ALE format")
        
        spreadsheet_path = Path(spreadsheet_path)
        
        # Determine output path if not specified
        if output_path is None:
            output_path = spreadsheet_path.with_suffix('.ale')
        else:
            output_path = Path(output_path)
        
        try:
            # Read the spreadsheet file
            if spreadsheet_path.suffix.lower() in ['.xlsx', '.xls', '.xlsm']:
                try:
                    import openpyxl
                    df = pd.read_excel(spreadsheet_path, dtype=str)
                except ImportError:
                    print("Excel import requires openpyxl. Install with: pip install openpyxl")
                    return None
            else:
                df = pd.read_csv(spreadsheet_path, dtype=str)
            
            # Fill NaN values with empty strings
            df.fillna('', inplace=True)
            
            print(f"Read {len(df)} rows from spreadsheet")
            
            # Add a "null" row at the bottom (required for ALE format)
            df = df._append(pd.Series("null", index=df.columns), ignore_index=True)
            
            # Get ALE header structure
            if template_ale_path:
                template_path = Path(template_ale_path)
                with open(template_path, 'r') as f:
                    template_content = f.read()
                    
                # Extract the header (everything before Column section)
                column_start_index = template_content.find("\nColumn")
                if column_start_index == -1:
                    # Use default header if template doesn't have proper structure
                    header_section = "Heading\nFIELD_DELIM\tTABS\nVIDEO_FORMAT\t1080\nAUDIO_FORMAT\t48khz\nFPS\t23.976"
                else:
                    header_section = template_content[:column_start_index]
            else:
                # Use default header
                header_section = "Heading\nFIELD_DELIM\tTABS\nVIDEO_FORMAT\t1080\nAUDIO_FORMAT\t48khz\nFPS\t23.976"
            
            # Convert data to tab-separated format
            csv = df.to_csv(sep='\t', index=False)
            
            # Extract column names and data rows
            csv_header, csv_data = csv.split('\n', 1)
            
            # Assemble the ALE file
            column_section = "\nColumn\n" + csv_header
            data_marker = "\n\nData\n"
            
            # Clean up formatting issues in data
            csv_data = csv_data.replace('\"\"\"', '')  # Remove triple double quotes
            csv_data = csv_data.replace('\"\"', '\"')  # Remove double double quotes
            csv_data = csv_data.replace('\t\"', '\t')  # Remove leading double quotes
            csv_data = csv_data.replace('\"\t', '\t')  # Remove trailing double quotes
            
            # Create the new ALE content
            ale_content = header_section + column_section + data_marker + csv_data
            
            # Write the ALE file
            with open(output_path, 'w') as f:
                f.write(ale_content)
                
            print(f"Created ALE file: {output_path}")
            return str(output_path)
            
        except Exception as e:
            print(f"Error converting spreadsheet to ALE: {e}")
            return None

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Convert and merge ALE files with database data')
    
    # Add subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Parser for merge command (original functionality)
    merge_parser = subparsers.add_parser('merge', help='Merge ALE with database')
    merge_parser.add_argument('--ale', required=True, help='Path to the ALE file')
    merge_parser.add_argument('--db', required=True, help='Path to the database CSV/Excel file')
    merge_parser.add_argument('--output', help='Path for the output ALE file')
    merge_parser.add_argument('--custom-columns', help='Path to JSON file with custom column mappings')
    merge_parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose debug output')
    merge_parser.add_argument('--id-position', type=int, help='Manually set which component of filename to use as ID (0-based)')
    merge_parser.add_argument('--print-columns', action='store_true', help='Print column information and exit')
    merge_parser.add_argument('--mapping', action='store_true', help='Visualize the column mappings between CSV and ALE files')
    merge_parser.add_argument('--preview', action='store_true', help='Preview the conversion without writing the output file')
    
    # Parser for export command (new functionality)
    export_parser = subparsers.add_parser('export', help='Export ALE to CSV/Excel')
    export_parser.add_argument('--ale', required=True, help='Path to the ALE file')
    export_parser.add_argument('--output', help='Path for the output file')
    export_parser.add_argument('--format', choices=['csv', 'excel'], default='csv', help='Output format (default: csv)')
    
    # Parser for import command (new functionality)
    import_parser = subparsers.add_parser('convert', help='Import/Convert CSV/Excel to ALE')
    import_parser.add_argument('--spreadsheet', required=True, help='Path to the CSV/Excel file')
    import_parser.add_argument('--output', help='Path for the output ALE file')
    import_parser.add_argument('--template', help='Path to a template ALE file for header structure')
    
    return parser.parse_args()

def run_merge_command(args):
    """Run the original merge functionality"""
    # Create converter instance
    try:
        converter = ALEConverter(
            args.ale, 
            args.db, 
            getattr(args, 'output', None),
            getattr(args, 'verbose', False)
        )
    except AttributeError as e:
        print(e)
        print("Handling this error in a brute force way...")
        print("""Convert and merge ALE files with database data

positional arguments:
  {merge,export,import}
                        Command to execute
    merge               Merge ALE with database
    export              Export ALE to CSV/Excel
    convert              Import CSV/Excel to ALE

""")
        quit(1)

    # Add Excel-specific attributes if available
    if hasattr(args, 'sheet') and args.sheet:
        converter.sheet_name = args.sheet
    if hasattr(args, 'list_sheets') and args.list_sheets:
        converter.list_sheets = True
    
    # Read files first
    converter.read_files()
    
    # If --print-columns flag is set, print column info and exit
    if hasattr(args, 'print_columns') and args.print_columns:
        converter.print_column_info()
        sys.exit(0)
    
    # Rest of the merge functionality
    converter.clean_database()
    converter.clean_ale()
    converter.extract_db_ids()
    
    # If --id-position is specified, use manual ID extraction
    if hasattr(args, 'id_position') and args.id_position is not None:
        converter.set_manual_id_extraction(args.id_position)
    else:
        converter.extract_ale_ids()
    
    converter.merge_data()
    
    # If custom column mappings are provided, load them
    custom_mappings = None
    if hasattr(args, 'custom_columns') and args.custom_columns:
        try:
            with open(args.custom_columns, 'r') as f:
                custom_mappings = json.load(f)
            if 'columns_to_drop' in custom_mappings or 'columns_to_rename' in custom_mappings:
                print(f"Using custom column mappings from {args.custom_columns}")
            else:
                print(f"Error: Custom mappings file must contain 'columns_to_drop' and/or 'columns_to_rename'")
                sys.exit(1)
        except Exception as e:
            print(f"Error loading custom mappings: {e}")
            sys.exit(1)
    
    # Prepare columns for output
    if custom_mappings:
        columns_to_drop = custom_mappings.get('columns_to_drop')
        columns_to_rename = custom_mappings.get('columns_to_rename')
        converter.prepare_ale_columns(columns_to_drop, columns_to_rename)
    else:
        converter.prepare_ale_columns()
    
    # If --mapping flag is set, visualize column mappings
    if hasattr(args, 'mapping') and args.mapping:
        converter.visualize_mapping()
        if hasattr(args, 'preview') and args.preview:
            print("\nPreview mode enabled. No output file will be created.")
            sys.exit(0)
    
    # If --preview flag is set, exit without creating the output file
    if hasattr(args, 'preview') and args.preview:
        print("\nPreview mode enabled. No output file will be created.")
        sys.exit(0)
    
    # Continue with conversion
    converter.create_new_ale()
    output_path = converter.write_output()
    
    if output_path:
        print(f"Conversion complete. Output file: {output_path}")
    else:
        print("Warning: No output file was created.")
    
    # Show mapping at the end if requested
    if hasattr(args, 'mapping') and args.mapping:
        converter.visualize_mapping()

def main():
    """Main function to run the conversion process"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Check if we're using subcommands or legacy mode
    if hasattr(args, 'command') and args.command:
        # Using subcommands (export, import, merge)
        if args.command == 'export':
            # Export ALE to CSV/Excel
            converter = ALEConverter(args.ale, None, args.output)
            output_path = converter.export_ale_to_spreadsheet(
                args.ale,
                args.output,
                args.format
            )
            if output_path:
                print(f"Export complete. Output file: {output_path}")
            
        elif args.command == 'convert':
            # Import CSV/Excel to ALE
            output_path = ALEConverter.convert_spreadsheet_to_ale(
                args.spreadsheet,
                args.output,
                args.template
            )
            if output_path:
                print(f"Import complete. Output file: {output_path}")
        
        elif args.command == 'merge':
            # Merge command (with subcommand parser)
            run_merge_command(args)
    else:
        # Legacy mode (no subcommand)
        run_merge_command(args)


if __name__ == "__main__":
    main()
