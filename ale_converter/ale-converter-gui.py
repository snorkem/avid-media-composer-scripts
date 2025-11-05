import os
import sys
import json
import pandas as pd
from pathlib import Path
import threading
import queue
import re

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QComboBox, QTabWidget, QFileDialog, 
    QTextEdit, QGroupBox, QFormLayout, QLineEdit, QCheckBox, 
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
    QMessageBox, QProgressBar, QRadioButton, QButtonGroup, QDialog,
    QListWidget, QAbstractItemView, QGridLayout, QSpinBox, QAction,
    QMenuBar, QToolBar, QStatusBar, QStyle, QSizePolicy, QScrollArea,
    QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer, QSettings
from PyQt5.QtGui import QIcon, QFont, QColor, QPalette

# Import the ALEConverter class from the ale_converter.py module
try:
    from ale_converter import ALEConverter
except ImportError:
    # If the script is run from a different directory, try to find the module
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Add the directory to the Python path
    sys.path.append(script_dir)
    try:
        from ale_converter import ALEConverter
    except ImportError:
        print("Error: Could not import ALEConverter from ale_converter.py")
        print("Make sure the script is in the same directory as ale_converter.py")
        sys.exit(1)

# Valid FPS values as defined in the original script
VALID_FPS_VALUES = [23.976, 29.97, 59.94, 24, 25, 30, 60, 119.88, 120]

class LogRedirector:
    """Class to redirect print statements to the GUI log box"""
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.queue = queue.Queue()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_log)
        self.timer.start(100)  # Update the log every 100ms
        
    def write(self, text):
        self.queue.put(text)
        
    def flush(self):
        pass
        
    def update_log(self):
        while not self.queue.empty():
            text = self.queue.get()
            self.text_widget.append(text.rstrip())
            self.text_widget.ensureCursorVisible()

class ConverterWorker(QThread):
    """Worker thread for running conversions without freezing the GUI"""
    update_log = pyqtSignal(str)
    finished = pyqtSignal(bool, str)  # Success flag, message
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.command = None
        self.args = {}
        self.converter = None
        
    def run(self):
        try:
            if self.command == 'merge':
                # Create converter instance
                self.converter = ALEConverter(
                    self.args.get('ale_path'),
                    self.args.get('db_path'),
                    self.args.get('output_path'),
                    True  # Always verbose for the GUI
                )

                # Get parameters
                id_position = self.args.get('id_position')
                custom_mappings = self.args.get('custom_mappings')

                # Run the conversion using the new refactored API
                output_path = self.converter.convert_with_merge(
                    id_position=id_position,
                    column_mapping_config=custom_mappings
                )

                self.finished.emit(True, f"Conversion complete. Output file: {output_path}")
                
            elif self.command == 'export':
                output_path = ALEConverter.export_ale_to_spreadsheet(
                    self.args.get('ale_path'),
                    self.args.get('output_path'),
                    self.args.get('format', 'csv'),  # Note: parameter name in API is 'output_format'
                    self.args.get('fps', 23.976),
                    verbose=True
                )
                
                if output_path:
                    self.finished.emit(True, f"Export complete. Output file: {output_path}")
                else:
                    self.finished.emit(False, "Export failed. See log for details.")
                    
            elif self.command == 'convert':
                output_path = ALEConverter.convert_spreadsheet_to_ale(
                    self.args.get('spreadsheet_path'),
                    self.args.get('output_path'),
                    self.args.get('template_path'),
                    self.args.get('fps')
                )
                
                if output_path:
                    self.finished.emit(True, f"Import complete. Output file: {output_path}")
                else:
                    self.finished.emit(False, "Import failed. See log for details.")
                    
        except Exception as e:
            import traceback
            error_msg = f"Error during {self.command}: {str(e)}\n{traceback.format_exc()}"
            self.update_log.emit(error_msg)
            self.finished.emit(False, f"Operation failed: {str(e)}")

class ColumnMapDialog(QDialog):
    """Dialog for mapping and dropping columns"""
    def __init__(self, db_columns, parent=None):
        super().__init__(parent)
        self.db_columns = db_columns
        self.column_mappings = {}
        self.columns_to_drop = []
        
        self.setWindowTitle("Column Mapping")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Table for column mappings
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Database Column", "Action", "ALE Column Name"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Populate the table with database columns
        self.table.setRowCount(len(self.db_columns))
        for i, col in enumerate(self.db_columns):
            # Database column name
            item = QTableWidgetItem(col)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Make it read-only
            self.table.setItem(i, 0, item)
            
            # Action combo box (Keep/Drop)
            action_combo = QComboBox()
            action_combo.addItems(["Keep", "Drop"])
            action_combo.setProperty("row", i)
            action_combo.currentIndexChanged.connect(self.action_changed)
            self.table.setCellWidget(i, 1, action_combo)
            
            # ALE column name (editable if action is "Keep")
            name_item = QTableWidgetItem(col)
            self.table.setItem(i, 2, name_item)
            
        # Buttons
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        
        layout.addWidget(QLabel("Configure how database columns should be mapped to ALE columns:"))
        layout.addWidget(self.table)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
    def action_changed(self):
        """Enable/disable ALE column name based on action selection"""
        combo = self.sender()
        row = combo.property("row")
        
        # If action is "Drop", disable ALE column name editing
        if combo.currentText() == "Drop":
            item = self.table.item(row, 2)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setBackground(QColor(240, 240, 240))
        else:
            item = self.table.item(row, 2)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            item.setBackground(QColor(255, 255, 255))
    
    def get_mappings(self):
        """Get the column mappings and drop list from the dialog"""
        columns_to_drop = []
        columns_to_rename = {}
        
        for i in range(self.table.rowCount()):
            db_col = self.table.item(i, 0).text()
            action = self.table.cellWidget(i, 1).currentText()
            
            if action == "Drop":
                columns_to_drop.append(db_col)
            else:
                ale_col = self.table.item(i, 2).text()
                # Only add to rename dict if names are different
                if db_col != ale_col:
                    columns_to_rename[db_col] = ale_col
        
        return {
            "columns_to_drop": columns_to_drop,
            "columns_to_rename": columns_to_rename
        }

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ALE Converter GUI")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        
        # Initialize instance variables
        self.db_data = None
        self.ale_data = None
        self.column_mappings = None
        
        # Create the UI
        self.init_ui()
        
        # Initialize settings
        self.settings = QSettings("ALEConverter", "GUI")
        self.load_settings()
        
        # Setup the converter worker thread
        self.worker = ConverterWorker()
        self.worker.update_log.connect(self.append_log)
        self.worker.finished.connect(self.conversion_finished)
        
        # Redirect stdout to log
        self.log_redirector = LogRedirector(self.log_text)
        self.original_stdout = sys.stdout
        sys.stdout = self.log_redirector
        
    def init_ui(self):
        # Central widget and layout
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Create a tab widget
        self.tabs = QTabWidget()
        self.merge_tab = QWidget()
        self.export_tab = QWidget()
        self.convert_tab = QWidget()
        
        self.tabs.addTab(self.merge_tab, "Merge")
        self.tabs.addTab(self.export_tab, "Export")
        self.tabs.addTab(self.convert_tab, "Convert")
        
        # Setup each tab
        self.setup_merge_tab()
        self.setup_export_tab()
        self.setup_convert_tab()
        
        # Log area
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        
        # Add status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Add progress bar to status bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # Add components to the main layout
        main_layout.addWidget(self.tabs)
        main_layout.addWidget(log_group, 1)  # Give the log area more space
        
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # Setup menu bar
        self.setup_menu()
        
    def setup_menu(self):
        """Setup the menu bar"""
        menu_bar = self.menuBar()
        
        # File menu
        file_menu = menu_bar.addMenu("File")
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menu_bar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def setup_merge_tab(self):
        """Setup the UI for the Merge tab"""
        layout = QVBoxLayout()
        
        # File selection group
        file_group = QGroupBox("Files")
        file_layout = QFormLayout()
        
        # ALE file selection
        ale_layout = QHBoxLayout()
        self.ale_path_edit = QLineEdit()
        self.ale_path_edit.setPlaceholderText("Path to ALE file")
        ale_browse_btn = QPushButton("Browse...")
        ale_browse_btn.clicked.connect(self.browse_ale_file)
        ale_layout.addWidget(self.ale_path_edit)
        ale_layout.addWidget(ale_browse_btn)
        file_layout.addRow("ALE File:", ale_layout)
        
        # Database file selection
        db_layout = QHBoxLayout()
        self.db_path_edit = QLineEdit()
        self.db_path_edit.setPlaceholderText("Path to database file (CSV/Excel)")
        db_browse_btn = QPushButton("Browse...")
        db_browse_btn.clicked.connect(self.browse_db_file)
        db_layout.addWidget(self.db_path_edit)
        db_layout.addWidget(db_browse_btn)
        file_layout.addRow("Database:", db_layout)
        
        # Output file selection
        output_layout = QHBoxLayout()
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText("Path to output ALE file")
        output_browse_btn = QPushButton("Browse...")
        output_browse_btn.clicked.connect(self.browse_output_file)
        output_layout.addWidget(self.output_path_edit)
        output_layout.addWidget(output_browse_btn)
        file_layout.addRow("Output:", output_layout)
        
        file_group.setLayout(file_layout)
        
        # Options group
        options_group = QGroupBox("Options")
        options_layout = QFormLayout()
        
        # FPS selection
        self.fps_combo = QComboBox()
        for fps in VALID_FPS_VALUES:
            self.fps_combo.addItem(str(fps))
        self.fps_combo.setCurrentText("23.976")  # Default
        options_layout.addRow("FPS:", self.fps_combo)
        
        # ID position selection
        self.id_position_spin = QSpinBox()
        self.id_position_spin.setRange(0, 10)
        self.id_position_spin.setValue(1)  # Default to second component (index 1)
        self.id_position_spin.setSpecialValueText("Auto")
        options_layout.addRow("ID Position:", self.id_position_spin)
        
        # Column mapping
        self.mapping_btn = QPushButton("Configure Column Mapping...")
        self.mapping_btn.clicked.connect(self.configure_column_mapping)
        options_layout.addRow("Mapping:", self.mapping_btn)
        
        options_group.setLayout(options_layout)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        preview_btn = QPushButton("Preview")
        preview_btn.clicked.connect(self.preview_merge)
        merge_btn = QPushButton("Merge")
        merge_btn.clicked.connect(self.run_merge)
        
        btn_layout.addWidget(preview_btn)
        btn_layout.addWidget(merge_btn)
        
        # Add everything to the layout
        layout.addWidget(file_group)
        layout.addWidget(options_group)
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        self.merge_tab.setLayout(layout)
        
        # Initially disable the mapping button until a database is loaded
        self.mapping_btn.setEnabled(False)
        
    def setup_export_tab(self):
        """Setup the UI for the Export tab"""
        layout = QVBoxLayout()
        
        # File selection group
        file_group = QGroupBox("Files")
        file_layout = QFormLayout()
        
        # ALE file selection
        ale_layout = QHBoxLayout()
        self.export_ale_path_edit = QLineEdit()
        self.export_ale_path_edit.setPlaceholderText("Path to ALE file")
        ale_browse_btn = QPushButton("Browse...")
        ale_browse_btn.clicked.connect(self.browse_export_ale_file)
        ale_layout.addWidget(self.export_ale_path_edit)
        ale_layout.addWidget(ale_browse_btn)
        file_layout.addRow("ALE File:", ale_layout)
        
        # Output file selection
        output_layout = QHBoxLayout()
        self.export_output_path_edit = QLineEdit()
        self.export_output_path_edit.setPlaceholderText("Path to output file")
        output_browse_btn = QPushButton("Browse...")
        output_browse_btn.clicked.connect(self.browse_export_output_file)
        output_layout.addWidget(self.export_output_path_edit)
        output_layout.addWidget(output_browse_btn)
        file_layout.addRow("Output:", output_layout)
        
        file_group.setLayout(file_layout)
        
        # Options group
        options_group = QGroupBox("Options")
        options_layout = QFormLayout()
        
        # Format selection
        self.export_format_combo = QComboBox()
        self.export_format_combo.addItems(["csv", "excel"])
        options_layout.addRow("Format:", self.export_format_combo)
        
        # FPS selection
        self.export_fps_combo = QComboBox()
        for fps in VALID_FPS_VALUES:
            self.export_fps_combo.addItem(str(fps))
        self.export_fps_combo.setCurrentText("23.976")  # Default
        options_layout.addRow("FPS:", self.export_fps_combo)
        
        options_group.setLayout(options_layout)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self.run_export)
        
        btn_layout.addWidget(export_btn)
        
        # Add everything to the layout
        layout.addWidget(file_group)
        layout.addWidget(options_group)
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        self.export_tab.setLayout(layout)
        
    def setup_convert_tab(self):
        """Setup the UI for the Convert tab"""
        layout = QVBoxLayout()
        
        # File selection group
        file_group = QGroupBox("Files")
        file_layout = QFormLayout()
        
        # Spreadsheet file selection
        spreadsheet_layout = QHBoxLayout()
        self.spreadsheet_path_edit = QLineEdit()
        self.spreadsheet_path_edit.setPlaceholderText("Path to CSV/Excel file")
        spreadsheet_browse_btn = QPushButton("Browse...")
        spreadsheet_browse_btn.clicked.connect(self.browse_spreadsheet_file)
        spreadsheet_layout.addWidget(self.spreadsheet_path_edit)
        spreadsheet_layout.addWidget(spreadsheet_browse_btn)
        file_layout.addRow("Spreadsheet:", spreadsheet_layout)
        
        # Output file selection
        output_layout = QHBoxLayout()
        self.convert_output_path_edit = QLineEdit()
        self.convert_output_path_edit.setPlaceholderText("Path to output ALE file")
        output_browse_btn = QPushButton("Browse...")
        output_browse_btn.clicked.connect(self.browse_convert_output_file)
        output_layout.addWidget(self.convert_output_path_edit)
        output_layout.addWidget(output_browse_btn)
        file_layout.addRow("Output:", output_layout)
        
        # Template file selection
        template_layout = QHBoxLayout()
        self.template_path_edit = QLineEdit()
        self.template_path_edit.setPlaceholderText("Path to template ALE file (optional)")
        template_browse_btn = QPushButton("Browse...")
        template_browse_btn.clicked.connect(self.browse_template_file)
        template_layout.addWidget(self.template_path_edit)
        template_layout.addWidget(template_browse_btn)
        file_layout.addRow("Template:", template_layout)
        
        file_group.setLayout(file_layout)
        
        # Options group
        options_group = QGroupBox("Options")
        options_layout = QFormLayout()
        
        # FPS selection
        self.convert_fps_combo = QComboBox()
        for fps in VALID_FPS_VALUES:
            self.convert_fps_combo.addItem(str(fps))
        self.convert_fps_combo.setCurrentText("23.976")  # Default
        options_layout.addRow("FPS:", self.convert_fps_combo)
        
        options_group.setLayout(options_layout)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        preview_btn = QPushButton("Preview")
        preview_btn.clicked.connect(self.preview_convert)
        convert_btn = QPushButton("Convert")
        convert_btn.clicked.connect(self.run_convert)
        
        btn_layout.addWidget(preview_btn)
        btn_layout.addWidget(convert_btn)
        
        # Add everything to the layout
        layout.addWidget(file_group)
        layout.addWidget(options_group)
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        self.convert_tab.setLayout(layout)
        
    def browse_ale_file(self):
        """Browse for an ALE file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select ALE File", "", "ALE Files (*.ale);;All Files (*)"
        )
        if file_path:
            self.ale_path_edit.setText(file_path)
            
    def browse_export_ale_file(self):
        """Browse for an ALE file for export"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select ALE File", "", "ALE Files (*.ale);;All Files (*)"
        )
        if file_path:
            self.export_ale_path_edit.setText(file_path)
            
            # Suggest default output file
            default_output = Path(file_path).with_suffix('.csv')
            self.export_output_path_edit.setText(str(default_output))

    def configure_column_mapping(self):
        """Open the column mapping dialog"""
        if not hasattr(self, 'db_columns') or not self.db_columns:
            QMessageBox.warning(self, "Error", "Please load a database file first.")
            return
            
        # Create a simple converter-like object to hold the data and mappings
        class SimpleConverter:
            pass
            
        converter = SimpleConverter()
        converter.df_db = self.db_data
        
        # Add current column mappings if available
        if self.column_mappings:
            converter.column_mappings = self.column_mappings
            
        # Display the preview dialog with editing enabled, but only the mapping tab
        preview_dialog = PreviewDialog(converter, True, self)
        preview_dialog.setWindowTitle("Configure Column Mapping")
        
        # Keep only the mapping tab
        while preview_dialog.tabs.count() > 1:
            preview_dialog.tabs.removeTab(0)  # Remove all tabs except the last one (mapping)
            
        result = preview_dialog.exec_()
        
        # If dialog was accepted and changes were made, update the column mappings
        if result == QDialog.Accepted and preview_dialog.column_mappings:
            self.column_mappings = preview_dialog.column_mappings
            
            # Display summary
            drop_count = len(self.column_mappings.get('columns_to_drop', []))
            rename_count = len(self.column_mappings.get('columns_to_rename', {}))
            
            QMessageBox.information(
                self, 
                "Column Mapping", 
                f"Configuration saved.\n\n"
                f"Columns to drop: {drop_count}\n"
                f"Columns to rename: {rename_count}"
            )

    def browse_db_file(self):
        """Browse for a database file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Database File", "", 
            "CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        if file_path:
            self.db_path_edit.setText(file_path)
            
            # Load the database to get column info
            try:
                self.load_db_preview(file_path)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not load database file: {str(e)}")
            
    def browse_output_file(self):
        """Browse for output file location for merge"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Select Output File", "", "ALE Files (*.ale);;All Files (*)"
        )
        if file_path:
            # Add .ale extension if not present
            if not file_path.lower().endswith('.ale'):
                file_path += '.ale'
            self.output_path_edit.setText(file_path)
            
    def browse_export_output_file(self):
        """Browse for output file location for export"""
        format_ext = ".xlsx" if self.export_format_combo.currentText() == "excel" else ".csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Select Output File", "", 
            f"CSV Files (*.csv);;Excel Files (*.xlsx);;All Files (*)"
        )
        if file_path:
            # Add appropriate extension if not present
            if not file_path.lower().endswith(format_ext):
                file_path += format_ext
            self.export_output_path_edit.setText(file_path)
            
    def browse_spreadsheet_file(self):
        """Browse for a spreadsheet file for conversion"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Spreadsheet File", "", 
            "CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        if file_path:
            self.spreadsheet_path_edit.setText(file_path)
            
            # Suggest default output file
            default_output = Path(file_path).with_suffix('.ale')
            self.convert_output_path_edit.setText(str(default_output))
            
    def browse_convert_output_file(self):
        """Browse for output file location for convert"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Select Output File", "", "ALE Files (*.ale);;All Files (*)"
        )
        if file_path:
            # Add .ale extension if not present
            if not file_path.lower().endswith('.ale'):
                file_path += '.ale'
            self.convert_output_path_edit.setText(file_path)    

    def browse_template_file(self):
        """Browse for a template ALE file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Template ALE File", "", "ALE Files (*.ale);;All Files (*)"
        )
        if file_path:
            self.template_path_edit.setText(file_path)
            
    def load_db_preview(self, file_path):
        """Load a preview of the database file to get column info"""
        print(f"Loading database preview: {file_path}")
        
        # Check file type and load accordingly
        file_ext = Path(file_path).suffix.lower()
        if file_ext in ['.xlsx', '.xls', '.xlsm']:
            try:
                self.db_data = pd.read_excel(file_path, dtype=str, nrows=10)
            except Exception as e:
                print(f"Error reading Excel file: {e}")
                QMessageBox.warning(self, "Error", f"Error reading Excel file: {str(e)}")
                return
        else:
            try:
                # Default to CSV
                self.db_data = pd.read_csv(file_path, dtype=str, nrows=10)
            except Exception as e:
                print(f"Error reading CSV file: {e}")
                QMessageBox.warning(self, "Error", f"Error reading CSV file: {str(e)}")
                return
                
        # Store column names
        self.db_columns = self.db_data.columns.tolist()
        print(f"Loaded database with columns: {self.db_columns}")
        
        # Enable column mapping button
        self.mapping_btn.setEnabled(True)

    def validate_merge_inputs(self, preview=False):
        """Validate inputs for merge operation"""
        # Check required files
        ale_path = self.ale_path_edit.text()
        if not ale_path:
            QMessageBox.warning(self, "Input Error", "Please select an ALE file.")
            return False
            
        db_path = self.db_path_edit.text()
        if not db_path:
            QMessageBox.warning(self, "Input Error", "Please select a database file.")
            return False
            
        # Check output path only if not in preview mode
        if not preview:
            output_path = self.output_path_edit.text()
            if not output_path:
                QMessageBox.warning(self, "Input Error", "Please select an output file path.")
                return False
                
        # Check if files exist
        if not os.path.exists(ale_path):
            QMessageBox.warning(self, "Input Error", f"ALE file not found: {ale_path}")
            return False
            
        if not os.path.exists(db_path):
            QMessageBox.warning(self, "Input Error", f"Database file not found: {db_path}")
            return False
            
        return True
    
    def preview_convert(self):
        """Preview the convert operation"""
        if not self.validate_convert_inputs(preview=True):
            return
            
        try:
            # Load the spreadsheet to get column info
            file_path = self.spreadsheet_path_edit.text()
            file_ext = Path(file_path).suffix.lower()
            
            if file_ext in ['.xlsx', '.xls', '.xlsm']:
                try:
                    data = pd.read_excel(file_path, dtype=str, nrows=10)
                except Exception as e:
                    self.append_log(f"Error reading Excel file: {e}")
                    QMessageBox.warning(self, "Error", f"Error reading Excel file: {str(e)}")
                    return
            else:
                try:
                    # Default to CSV
                    data = pd.read_csv(file_path, dtype=str, nrows=10)
                except Exception as e:
                    self.append_log(f"Error reading CSV file: {e}")
                    QMessageBox.warning(self, "Error", f"Error reading CSV file: {str(e)}")
                    return
            
            # Create a simple converter-like object to hold the data
            class SimpleConverter:
                pass
                
            converter = SimpleConverter()
            converter.df_db = data
            
            # Display the preview dialog (without editing since it's a simple preview)
            preview_dialog = PreviewDialog(converter, False, self)
            preview_dialog.tabs.removeTab(1)  # Remove ALE tab
            preview_dialog.tabs.removeTab(1)  # Remove Merged tab (now at index 1)
            preview_dialog.tabs.removeTab(1)  # Remove Mapping tab (now at index 1)
            preview_dialog.exec_()
            
            self.append_log("\nPreview complete. No output file was created.")
        except Exception as e:
            print(e)

    def preview_merge(self):
        """Preview the merge operation"""
        # Make sure we have the necessary files
        if not self.validate_merge_inputs(preview=True):
            return

        # Simple preview - just show info about the files
        try:
            ale_path = self.ale_path_edit.text()
            db_path = self.db_path_edit.text()

            self.append_log("\n=== PREVIEW MODE ===")
            self.append_log(f"ALE File: {ale_path}")
            self.append_log(f"Database File: {db_path}")

            # Read just enough to show what will be processed
            from pathlib import Path
            from src.io.ale_reader import ALEReader
            from src.io.spreadsheet_io import SpreadsheetReader

            ale_data = ALEReader.read_file(Path(ale_path), verbose=True)
            self.append_log(f"\nALE file contains {len(ale_data.data)} clips")
            self.append_log(f"ALE columns: {', '.join(ale_data.data.columns.tolist()[:5])}...")

            reader = SpreadsheetReader()
            db_df = reader.read_file(Path(db_path), verbose=True)
            self.append_log(f"\nDatabase contains {len(db_df)} records")
            self.append_log(f"Database columns: {', '.join(db_df.columns.tolist()[:5])}...")

            self.append_log("\n=== Preview complete. Use 'Merge' button to process files. ===")

        except Exception as e:
            import traceback
            error_msg = f"Error during preview: {str(e)}\n{traceback.format_exc()}"
            self.append_log(error_msg)
            QMessageBox.critical(self, "Preview Error", f"Preview failed: {str(e)}")
        
    def run_merge(self):
        """Run the merge operation"""
        if not self.validate_merge_inputs():
            return
            
        # Get input values
        ale_path = self.ale_path_edit.text()
        db_path = self.db_path_edit.text()
        output_path = self.output_path_edit.text()
        fps = float(self.fps_combo.currentText())
        
        # Get ID position (None for auto)
        id_position = None
        if self.id_position_spin.value() > 0:
            id_position = self.id_position_spin.value() - 1
            
        # Start the worker thread
        self.append_log(f"\nStarting merge operation...")
        self.append_log(f"ALE file: {ale_path}")
        self.append_log(f"Database file: {db_path}")
        self.append_log(f"Output file: {output_path}")
        self.append_log(f"FPS: {fps}")
        if id_position is not None:
            self.append_log(f"ID Position: {id_position}")
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        # Configure and start the worker
        self.worker.command = 'merge'
        self.worker.args = {
            'ale_path': ale_path,
            'db_path': db_path,
            'output_path': output_path,
            'fps': fps,
            'id_position': id_position,
            'custom_mappings': self.column_mappings
        }
        self.worker.start()

    def run_export(self):
        """Run the export operation"""
        if not self.validate_export_inputs():
            return
            
        # Get input values
        ale_path = self.export_ale_path_edit.text()
        output_path = self.export_output_path_edit.text()
        export_format = self.export_format_combo.currentText()
        fps = float(self.export_fps_combo.currentText())
        
        # Start the worker thread
        self.append_log(f"\nStarting export operation...")
        self.append_log(f"ALE file: {ale_path}")
        self.append_log(f"Output file: {output_path}")
        self.append_log(f"Format: {export_format}")
        self.append_log(f"FPS: {fps}")
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        # Configure and start the worker
        self.worker.command = 'export'
        self.worker.args = {
            'ale_path': ale_path,
            'output_path': output_path,
            'format': export_format,
            'fps': fps
        }
        self.worker.start()

    def validate_convert_inputs(self, preview=False):
        """Validate inputs for convert operation"""
        # Check required files
        spreadsheet_path = self.spreadsheet_path_edit.text()
        if not spreadsheet_path:
            QMessageBox.warning(self, "Input Error", "Please select a spreadsheet file.")
            return False
            
        # Check output path only if not in preview mode
        if not preview:
            output_path = self.convert_output_path_edit.text()
            if not output_path:
                QMessageBox.warning(self, "Input Error", "Please select an output file path.")
                return False
                
        # Check if files exist
        if not os.path.exists(spreadsheet_path):
            QMessageBox.warning(self, "Input Error", f"Spreadsheet file not found: {spreadsheet_path}")
            return False
            
        # Check template file if specified
        template_path = self.template_path_edit.text()
        if template_path and not os.path.exists(template_path):
            QMessageBox.warning(self, "Input Error", f"Template file not found: {template_path}")
            return False
            
        return True

    def run_convert(self):
        """Run the convert operation"""
        if not self.validate_convert_inputs():
            return
            
        # Get input values
        spreadsheet_path = self.spreadsheet_path_edit.text()
        output_path = self.convert_output_path_edit.text()
        template_path = self.template_path_edit.text() if self.template_path_edit.text() else None
        fps = float(self.convert_fps_combo.currentText())
        
        # Start the worker thread
        self.append_log(f"\nStarting convert operation...")
        self.append_log(f"Spreadsheet file: {spreadsheet_path}")
        self.append_log(f"Output file: {output_path}")
        if template_path:
            self.append_log(f"Template file: {template_path}")
        self.append_log(f"FPS: {fps}")
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        # Configure and start the worker
        self.worker.command = 'convert'
        self.worker.args = {
            'spreadsheet_path': spreadsheet_path,
            'output_path': output_path,
            'template_path': template_path,
            'fps': fps
        }
        self.worker.start()

    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self, 
            "About ALE Converter GUI",
            "<h3>ALE Converter GUI</h3>"
            "<p>A graphical interface for the ALE Converter script.</p>"
            "<p>This application provides a user-friendly way to:</p>"
            "<ul>"
            "<li>Merge ALE files with metadata from a database</li>"
            "<li>Export ALE files to CSV or Excel format</li>"
            "<li>Convert CSV or Excel files to ALE format</li>"
            "</ul>"
            "<p>Built with PyQt5.</p>"
        )

    def load_settings(self):
        """Load saved settings"""
        # Restore window geometry
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
            
        # Restore FPS settings
        fps = self.settings.value("fps")
        if fps:
            index = self.fps_combo.findText(fps)
            if index >= 0:
                self.fps_combo.setCurrentIndex(index)
                
            index = self.export_fps_combo.findText(fps)
            if index >= 0:
                self.export_fps_combo.setCurrentIndex(index)
                
            index = self.convert_fps_combo.findText(fps)
            if index >= 0:
                self.convert_fps_combo.setCurrentIndex(index)

    def save_settings(self):
        """Save settings"""
        # Save window geometry
        self.settings.setValue("geometry", self.saveGeometry())
        
        # Save FPS settings
        self.settings.setValue("fps", self.fps_combo.currentText())

    def closeEvent(self, event):
        """Handle application close event"""
        # Save settings
        self.save_settings()
        
        # Restore original stdout
        sys.stdout = self.original_stdout
        
        # Accept the close event
        event.accept()

    def append_log(self, text):
        """Append text to the log display"""
        self.log_text.append(text)
        # Scroll to the bottom
        self.log_text.ensureCursorVisible()

    def conversion_finished(self, success, message):
        """Handle conversion completion"""
        # Hide progress bar
        self.progress_bar.setVisible(False)
        
        # Update status bar
        if success:
            self.status_bar.showMessage(message, 5000)
            QMessageBox.information(self, "Operation Complete", message)
        else:
            self.status_bar.showMessage("Operation failed", 5000)
            QMessageBox.critical(self, "Operation Failed", message)

class PreviewDialog(QDialog):
    """Dialog for displaying column mapping preview in a more structured format"""
    def __init__(self, converter, allow_editing=True, parent=None):
        super().__init__(parent)
        self.converter = converter
        self.allow_editing = allow_editing
        self.column_mappings = None
        self.setWindowTitle("Column Mapping Preview")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        
        self.init_ui()
        self.load_data()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Create a tab widget for different views
        self.tabs = QTabWidget()
        
        # Tab for database columns
        self.db_tab = QWidget()
        self.tabs.addTab(self.db_tab, "Database Columns")
        
        # Tab for ALE columns
        self.ale_tab = QWidget()
        self.tabs.addTab(self.ale_tab, "ALE Columns")
        
        # Tab for merged columns
        self.merged_tab = QWidget()
        self.tabs.addTab(self.merged_tab, "Merged Data")
        
        # Tab for mapping visualization/editing
        self.mapping_tab = QWidget()
        self.tabs.addTab(self.mapping_tab, "Column Mapping")
        
        # Setup each tab
        self.setup_db_tab()
        self.setup_ale_tab()
        self.setup_merged_tab()
        self.setup_mapping_tab()
        
        # Buttons at the bottom
        btn_layout = QHBoxLayout()
        
        if self.allow_editing:
            self.apply_btn = QPushButton("Apply Changes")
            self.apply_btn.clicked.connect(self.apply_changes)
            btn_layout.addWidget(self.apply_btn)
            
            # Add a reset button
            self.reset_btn = QPushButton("Reset Changes")
            self.reset_btn.clicked.connect(self.load_data)
            btn_layout.addWidget(self.reset_btn)
            
            btn_layout.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)
        
        layout.addWidget(self.tabs)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
    def setup_db_tab(self):
        """Setup the database columns tab"""
        layout = QVBoxLayout()
        
        # Label with information
        layout.addWidget(QLabel("Database columns from the CSV/Excel file:"))
        
        # Table for displaying database columns
        self.db_table = QTableWidget()
        self.db_table.setColumnCount(2)
        self.db_table.setHorizontalHeaderLabels(["Column Name", "Sample Value"])
        self.db_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.db_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        
        layout.addWidget(self.db_table)
        
        self.db_tab.setLayout(layout)
        
    def setup_ale_tab(self):
        """Setup the ALE columns tab"""
        layout = QVBoxLayout()
        
        # Label with information
        layout.addWidget(QLabel("Original ALE columns:"))
        
        # Table for displaying ALE columns
        self.ale_table = QTableWidget()
        self.ale_table.setColumnCount(2)
        self.ale_table.setHorizontalHeaderLabels(["Column Name", "Sample Value"])
        self.ale_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.ale_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        
        layout.addWidget(self.ale_table)
        
        self.ale_tab.setLayout(layout)
        
    def setup_merged_tab(self):
        """Setup the merged data tab"""
        layout = QVBoxLayout()
        
        # Label with information
        layout.addWidget(QLabel("Merged data columns (final ALE output):"))
        
        # Table for displaying merged columns
        self.merged_table = QTableWidget()
        self.merged_table.setColumnCount(2)
        self.merged_table.setHorizontalHeaderLabels(["Column Name", "Sample Value"])
        self.merged_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.merged_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        
        layout.addWidget(self.merged_table)
        
        self.merged_tab.setLayout(layout)
        
    def setup_mapping_tab(self):
        """Setup the mapping visualization/editing tab with JSON editing capability"""
        layout = QVBoxLayout()
        
        # Create a tab widget for different mapping views
        self.mapping_view_tabs = QTabWidget()
        
        # First tab - Visual editor (table view)
        visual_tab = QWidget()
        visual_layout = QVBoxLayout()
        
        if self.allow_editing:
            info_label = QLabel("Edit column mappings below. Set action to 'Drop' to exclude a column, or 'Keep' to include it.")
        else:
            info_label = QLabel("Column mapping from database to ALE:")
        visual_layout.addWidget(info_label)
        
        # Table for displaying/editing mapping
        self.mapping_table = QTableWidget()
        self.mapping_table.setColumnCount(3)
        self.mapping_table.setHorizontalHeaderLabels(["Database Column", "ALE Column Name", "Action"])
        self.mapping_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.mapping_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.mapping_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        
        visual_layout.addWidget(self.mapping_table)
        visual_tab.setLayout(visual_layout)
        
        # Second tab - JSON editor
        json_tab = QWidget()
        json_layout = QVBoxLayout()
        
        json_info_label = QLabel("Edit the JSON mapping directly. This allows for more advanced configurations.")
        json_layout.addWidget(json_info_label)
        
        self.json_editor = QTextEdit()
        self.json_editor.setFont(QFont("Courier", 10))  # Use monospace font for JSON
        
        json_layout.addWidget(self.json_editor)
        
        # Add JSON file import/export buttons
        if self.allow_editing:
            file_btn_layout = QHBoxLayout()
            
            import_json_btn = QPushButton("Import JSON File")
            import_json_btn.clicked.connect(self.import_json_file)
            
            export_json_btn = QPushButton("Export JSON File")
            export_json_btn.clicked.connect(self.export_json_file)
            
            file_btn_layout.addWidget(import_json_btn)
            file_btn_layout.addWidget(export_json_btn)
            
            json_layout.addLayout(file_btn_layout)
        
        # Add sync buttons
        if self.allow_editing:
            btn_layout = QHBoxLayout()
            
            update_from_json_btn = QPushButton("Update Table from JSON")
            update_from_json_btn.clicked.connect(self.update_table_from_json)
            
            update_to_json_btn = QPushButton("Update JSON from Table")
            update_to_json_btn.clicked.connect(self.update_json_from_table)
            
            btn_layout.addWidget(update_from_json_btn)
            btn_layout.addWidget(update_to_json_btn)
            
            json_layout.addLayout(btn_layout)
        
        json_tab.setLayout(json_layout)
        
        # Add tabs to the mapping view tabs widget
        self.mapping_view_tabs.addTab(visual_tab, "Visual Editor")
        self.mapping_view_tabs.addTab(json_tab, "JSON Editor")
        
        # Add the tabs widget to the main layout
        layout.addWidget(self.mapping_view_tabs)
        
        self.mapping_tab.setLayout(layout)
    
    def update_json_from_table(self):
        """Update JSON editor content based on the table's current state"""
        try:
            # Extract current mappings from the table
            columns_to_drop = []
            columns_to_rename = {}
            
            for i in range(self.mapping_table.rowCount()):
                db_col = self.mapping_table.item(i, 0).text()
                
                # Check if there's a combo box (editable mode)
                action_widget = self.mapping_table.cellWidget(i, 2)
                if action_widget and isinstance(action_widget, QComboBox):
                    action = action_widget.currentText()
                else:
                    action = self.mapping_table.item(i, 2).text()
                    
                if action == "Drop" or action == "Dropped":
                    columns_to_drop.append(db_col)
                else:
                    ale_col = self.mapping_table.item(i, 1).text()
                    # Only add to rename dict if names are different
                    if db_col != ale_col:
                        columns_to_rename[db_col] = ale_col
            
            # Create the mappings dictionary
            mappings = {
                'columns_to_drop': columns_to_drop,
                'columns_to_rename': columns_to_rename
            }
            
            # Format the JSON with nice indentation
            json_text = json.dumps(mappings, indent=4)
            self.json_editor.setText(json_text)
            
            # Update the stored mappings
            self.column_mappings = mappings.copy()
            
            QMessageBox.information(self, "Success", "JSON updated from table successfully")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update JSON: {str(e)}")

    def update_table_from_json(self):
        """Update table content based on the JSON editor"""
        try:
            # Get the JSON text
            json_text = self.json_editor.toPlainText()
            
            # Parse the JSON
            mappings = json.loads(json_text)
            
            # Validate the structure
            if not isinstance(mappings, dict):
                raise ValueError("JSON must be an object/dictionary")
                
            if 'columns_to_drop' not in mappings or not isinstance(mappings['columns_to_drop'], list):
                raise ValueError("JSON must contain a 'columns_to_drop' list")
                
            if 'columns_to_rename' not in mappings or not isinstance(mappings['columns_to_rename'], dict):
                raise ValueError("JSON must contain a 'columns_to_rename' dictionary")
            
            # Update the table
            columns_to_drop = mappings['columns_to_drop']
            columns_to_rename = mappings['columns_to_rename']
            
            # Update each row in the table
            for i in range(self.mapping_table.rowCount()):
                db_col = self.mapping_table.item(i, 0).text()
                
                # Get the action combo box
                action_combo = self.mapping_table.cellWidget(i, 2)
                if not action_combo or not isinstance(action_combo, QComboBox):
                    continue
                    
                # Get the ALE column name item
                name_item = self.mapping_table.item(i, 1)
                if not name_item:
                    continue
                    
                # Set action and name based on mappings
                if db_col in columns_to_drop:
                    action_combo.setCurrentText("Drop")
                    # Disable and clear ALE column name
                    name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
                    name_item.setBackground(QColor(240, 240, 240))
                    name_item.setText(db_col)  # Reset to default
                else:
                    action_combo.setCurrentText("Keep")
                    # Enable ALE column name editing
                    name_item.setFlags(name_item.flags() | Qt.ItemIsEditable)
                    name_item.setBackground(QColor(255, 255, 255))
                    
                    # Set rename if applicable
                    if db_col in columns_to_rename:
                        name_item.setText(columns_to_rename[db_col])
                    else:
                        name_item.setText(db_col)  # Reset to default
            
            # Update the stored mappings
            self.column_mappings = mappings.copy()
            
            QMessageBox.information(self, "Success", "Table updated from JSON successfully")
            
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON Error", f"Invalid JSON format: {str(e)}")
        except ValueError as e:
            QMessageBox.critical(self, "Validation Error", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update table: {str(e)}")

    def import_json_file(self):
        """Import column mappings from a JSON file"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Import JSON Mapping File", "", "JSON Files (*.json);;All Files (*)"
            )
            
            if not file_path:
                return  # User cancelled
                
            with open(file_path, 'r') as f:
                json_text = f.read()
                
            # Set the JSON editor text
            self.json_editor.setText(json_text)
            
            # Update the table from the imported JSON
            self.update_table_from_json()
            
            # Show success message
            QMessageBox.information(
                self, 
                "Import Successful", 
                f"Successfully imported mappings from {file_path}"
            )
            
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON Error", f"Invalid JSON format in file: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to import JSON file: {str(e)}")

    def export_json_file(self):
        """Export column mappings to a JSON file"""
        try:
            # First update the JSON from the table to ensure it's current
            self.update_json_from_table()
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export JSON Mapping File", "", "JSON Files (*.json);;All Files (*)"
            )
            
            if not file_path:
                return  # User cancelled
                
            # Add .json extension if not present
            if not file_path.lower().endswith('.json'):
                file_path += '.json'
                
            # Get the JSON text
            json_text = self.json_editor.toPlainText()
            
            # Validate the JSON by parsing it
            json.loads(json_text)
            
            # Write to file
            with open(file_path, 'w') as f:
                f.write(json_text)
                
            # Show success message
            QMessageBox.information(
                self, 
                "Export Successful", 
                f"Successfully exported mappings to {file_path}"
            )
            
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON Error", f"Invalid JSON format: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export JSON file: {str(e)}")

    def browse_ale_file(self):
        """Placeholder to prevent errors - this should be in MainWindow"""
        QMessageBox.warning(self, "Error", "This function is not available in the preview dialog.")

    def load_mapping_data(self):
        """Load mapping data into the mapping table"""
        # Get all database columns
        db_columns = []
        if hasattr(self.converter, 'df_db') and self.converter.df_db is not None:
            db_columns = self.converter.df_db.columns.tolist()
        # Update the JSON editor if it exists
        if hasattr(self, 'json_editor'):
            json_text = json.dumps(self.column_mappings, indent=4)
            self.json_editor.setText(json_text)
                
        # Clear existing data
        self.mapping_table.setRowCount(len(db_columns))
        
        # Try to get existing mappings from different sources
        columns_to_drop = []
        columns_to_rename = {}
        
        # Determine where to get the mappings from
        parent = self.parent()
        parent_has_mappings = (parent and hasattr(parent, 'column_mappings') and 
                               parent.column_mappings is not None and 
                               (len(parent.column_mappings.get('columns_to_drop', [])) > 0 or 
                                len(parent.column_mappings.get('columns_to_rename', {})) > 0))
        
        converter_has_mappings = (hasattr(self.converter, 'column_mappings') and 
                                  self.converter.column_mappings is not None)
        
        # First check parent for mappings
        if parent_has_mappings:
            print("Loading mappings from parent window")
            columns_to_drop = parent.column_mappings.get('columns_to_drop', [])
            columns_to_rename = parent.column_mappings.get('columns_to_rename', {})
        # Then check converter for mappings
        elif converter_has_mappings:
            print("Loading mappings from converter")
            if isinstance(self.converter.column_mappings, dict):
                # Dictionary with explicit mappings
                columns_to_drop = self.converter.column_mappings.get('columns_to_drop', [])
                columns_to_rename = self.converter.column_mappings.get('columns_to_rename', {})
            else:
                # Direct mapping dictionary (old format)
                for db_col, ale_col in self.converter.column_mappings.items():
                    if ale_col is None:
                        columns_to_drop.append(db_col)
                    elif db_col != ale_col:
                        columns_to_rename[db_col] = ale_col
        
        # Debug information
        print(f"Columns to drop: {columns_to_drop}")
        print(f"Columns to rename: {columns_to_rename}")
        
        # Populate the mapping table
        for i, db_col in enumerate(db_columns):
            # Database column name (read-only)
            item = QTableWidgetItem(db_col)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Make it read-only
            self.mapping_table.setItem(i, 0, item)
            
            # ALE column name (editable)
            ale_col = db_col
            if db_col in columns_to_rename:
                ale_col = columns_to_rename[db_col]
                
            name_item = QTableWidgetItem(ale_col)
            if not self.allow_editing:
                name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.mapping_table.setItem(i, 1, name_item)
            
            # Action combo box
            if self.allow_editing:
                action_combo = QComboBox()
                action_combo.addItems(["Keep", "Drop"])
                action_combo.setProperty("row", i)
                action_combo.currentIndexChanged.connect(self.action_changed)
                self.mapping_table.setCellWidget(i, 2, action_combo)
                
                # Set initial value based on saved mappings
                if db_col in columns_to_drop:
                    action_combo.setCurrentText("Drop")
                    # Disable ALE column name
                    name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
                    name_item.setBackground(QColor(240, 240, 240))
            else:
                # Read-only action text
                if db_col in columns_to_drop:
                    action_item = QTableWidgetItem("Dropped")
                    # Color the row red for dropped columns
                    for col in range(3):
                        if self.mapping_table.item(i, col):
                            self.mapping_table.item(i, col).setBackground(QColor(255, 200, 200))
                elif db_col in columns_to_rename:
                    action_item = QTableWidgetItem("Renamed")
                    # Color the row blue for renamed columns
                    for col in range(3):
                        if self.mapping_table.item(i, col):
                            self.mapping_table.item(i, col).setBackground(QColor(200, 200, 255))
                else:
                    action_item = QTableWidgetItem("Kept")
                action_item.setFlags(action_item.flags() & ~Qt.ItemIsEditable)
                self.mapping_table.setItem(i, 2, action_item)
                
        # Store initial column mappings for comparison and for returning
        self.column_mappings = {
            'columns_to_drop': columns_to_drop.copy(),
            'columns_to_rename': columns_to_rename.copy()
        }
        
    def load_data(self):
        """Load data from the converter into the tables"""
        # Load database columns
        if hasattr(self.converter, 'df_db') and self.converter.df_db is not None:
            df_db = self.converter.df_db
            self.db_table.setRowCount(len(df_db.columns))
            
            for i, col in enumerate(df_db.columns):
                # Column name
                self.db_table.setItem(i, 0, QTableWidgetItem(col))
                
                # Sample value (from first row if available)
                if len(df_db) > 0:
                    sample = str(df_db[col].iloc[0])
                    if len(sample) > 100:
                        sample = sample[:97] + "..."
                    self.db_table.setItem(i, 1, QTableWidgetItem(sample))
                else:
                    self.db_table.setItem(i, 1, QTableWidgetItem("N/A"))
        
        # Load ALE columns
        if hasattr(self.converter, 'df_ale') and self.converter.df_ale is not None:
            df_ale = self.converter.df_ale
            self.ale_table.setRowCount(len(df_ale.columns))
            
            for i, col in enumerate(df_ale.columns):
                # Column name
                self.ale_table.setItem(i, 0, QTableWidgetItem(col))
                
                # Sample value (from first row if available)
                if len(df_ale) > 0:
                    sample = str(df_ale[col].iloc[0])
                    if len(sample) > 100:
                        sample = sample[:97] + "..."
                    self.ale_table.setItem(i, 1, QTableWidgetItem(sample))
                else:
                    self.ale_table.setItem(i, 1, QTableWidgetItem("N/A"))
        
        # Load merged data columns
        if hasattr(self.converter, 'df_ale_db_exp') and self.converter.df_ale_db_exp is not None:
            df_merged = self.converter.df_ale_db_exp
            self.merged_table.setRowCount(len(df_merged.columns))
            
            for i, col in enumerate(df_merged.columns):
                # Column name
                self.merged_table.setItem(i, 0, QTableWidgetItem(col))
                
                # Sample value (from first row if available)
                if len(df_merged) > 0:
                    sample = str(df_merged[col].iloc[0])
                    if len(sample) > 100:
                        sample = sample[:97] + "..."
                    self.merged_table.setItem(i, 1, QTableWidgetItem(sample))
                else:
                    self.merged_table.setItem(i, 1, QTableWidgetItem("N/A"))
        
        # Load mapping information
        self.load_mapping_data()
        
    def action_changed(self):
        """Handle action combo box changes"""
        combo = self.sender()
        row = combo.property("row")
        
        # Get the ALE column name item
        name_item = self.mapping_table.item(row, 1)
        db_col = self.mapping_table.item(row, 0).text()
        
        # If action is "Drop", disable ALE column name editing
        if combo.currentText() == "Drop":
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            name_item.setBackground(QColor(240, 240, 240))
        else:
            name_item.setFlags(name_item.flags() | Qt.ItemIsEditable)
            name_item.setBackground(QColor(255, 255, 255))
            
            # Reset ALE column name to database column name if it was dropped
            if db_col in self.column_mappings['columns_to_drop']:
                name_item.setText(db_col)
                
    def apply_changes(self):
        """Apply the changes to the column mappings"""
        # Extract current mappings from the table
        columns_to_drop = []
        columns_to_rename = {}
        
        for i in range(self.mapping_table.rowCount()):
            db_col = self.mapping_table.item(i, 0).text()
            
            # Check if there's a combo box (editable mode)
            action_widget = self.mapping_table.cellWidget(i, 2)
            if action_widget:
                action = action_widget.currentText()
            else:
                action = self.mapping_table.item(i, 2).text()
                
            if action == "Drop" or action == "Dropped":
                columns_to_drop.append(db_col)
            else:
                ale_col = self.mapping_table.item(i, 1).text()
                # Only add to rename dict if names are different
                if db_col != ale_col:
                    columns_to_rename[db_col] = ale_col
        
        # Store the updated mappings
        self.column_mappings = {
            'columns_to_drop': columns_to_drop,
            'columns_to_rename': columns_to_rename
        }

        # Update the JSON editor to reflect changes
        if hasattr(self, 'json_editor'):
            json_text = json.dumps(self.column_mappings, indent=4)
            self.json_editor.setText(json_text)

        # Update the parent window's column mappings (if it exists)
        parent = self.parent()
        if parent and hasattr(parent, 'column_mappings'):
            parent.column_mappings = self.column_mappings.copy()
        
        # Provide a summary
        QMessageBox.information(
            self, 
            "Column Mapping Updated", 
            f"Configuration saved.\n\n"
            f"Columns to drop: {len(columns_to_drop)}\n"
            f"Columns to rename: {len(columns_to_rename)}"
        )
        
    def get_column_mappings(self):
        """Get the current column mappings"""
        # Make sure to get the latest state
        self.apply_changes()
        return self.column_mappings

    def accept(self):
        """Override accept to ensure column mappings are saved"""
        if self.allow_editing:
            self.apply_changes()  # Make sure changes are applied before closing
        super().accept()

    def reject(self):
        """Override reject to discard changes when Cancel is clicked"""
        # No need to save changes when rejecting the dialog
        # Just call the parent class's reject method
        super().reject()

def main():
    # Create application
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Use Fusion style for consistent look across platforms
    
    # Apply a stylesheet if desired
    app.setStyleSheet("""
        QGroupBox {
            font-weight: bold;
            border: 1px solid #aaa;
            border-radius: 5px;
            margin-top: 1ex;
            padding-top: 0.5ex;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top center;
            padding: 0 5px;
        }
        QPushButton {
            padding: 4px 15px;
        }
        QTextEdit {
            font-family: monospace;
        }
    """)
    
    # Create and show the main window
    window = MainWindow()
    window.show()
    
    # Run the application
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
