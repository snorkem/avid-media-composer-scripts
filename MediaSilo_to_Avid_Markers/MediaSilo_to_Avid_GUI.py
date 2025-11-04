import pandas as pd
import sys
import logging
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QTextEdit,
                             QFileDialog, QProgressBar, QGroupBox, QLineEdit,
                             QMessageBox)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QFont, QTextCursor

# Import shared functionality
from src.mediasilo_core import (
    combine_duplicate_timecodes,
    sanitize_comments, remove_unwanted_columns,
    format_marker_line, validate_required_columns
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mediasilo_conversion.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ConversionWorker(QThread):
    """Worker thread for file conversion to keep GUI responsive"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, input_path, output_path):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self._is_cancelled = False

    def cancel(self):
        """Request cancellation of the conversion"""
        self._is_cancelled = True

    def log_callback(self, message, level='info'):
        """Callback for shared functions to emit progress signals"""
        self.progress.emit(message)

    def run(self):
        try:
            self.progress.emit("=" * 60)
            self.progress.emit("Starting MediaSilo to Avid conversion")
            self.progress.emit(f"Input file: {self.input_path}")
            self.progress.emit(f"Output file: {self.output_path}")
            self.progress.emit("=" * 60)

            if self._is_cancelled:
                self.finished.emit(False, "Conversion cancelled")
                return

            # Load the CSV file
            self.progress.emit("Loading CSV file...")
            df = pd.read_csv(self.input_path)

            if self._is_cancelled:
                self.finished.emit(False, "Conversion cancelled")
                return

            self.progress.emit(f"Loaded {len(df)} rows")
            self.progress.emit(f"Columns: {list(df.columns)}")

            # Validate required columns
            is_valid, missing_required, missing_optional = validate_required_columns(df, self.log_callback)
            if not is_valid:
                error_msg = f"CSV is missing required columns: {', '.join(missing_required)}"
                self.finished.emit(False, error_msg)
                return

            # Remove unwanted columns
            df = remove_unwanted_columns(df, self.log_callback)

            # Combine duplicate timecodes
            df = combine_duplicate_timecodes(df, self.log_callback)

            # Sanitize Comment column
            df = sanitize_comments(df, self.log_callback)

            # Write output
            self.progress.emit("Writing Avid marker file...")
            with open(self.output_path, 'w', encoding='utf-8') as f:
                for i, (_, row) in enumerate(df.iterrows(), start=1):
                    line = format_marker_line(row)
                    f.write(line)

                    if i % 10 == 0:
                        self.progress.emit(f"Wrote {i}/{len(df)} markers...")

            self.progress.emit("=" * 60)
            self.progress.emit(f"Successfully wrote {len(df)} markers!")
            self.progress.emit("Conversion completed successfully!")
            self.progress.emit("=" * 60)

            self.finished.emit(True, f"Successfully converted {len(df)} markers")

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.progress.emit(error_msg)
            logger.error(error_msg, exc_info=True)
            self.finished.emit(False, error_msg)


class MediaSiloConverterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.input_path = ""
        self.output_path = ""
        self.worker = None
        self.initUI()

    def initUI(self):
        self.setWindowTitle('MediaSilo to Avid Marker Converter')
        self.setGeometry(100, 100, 800, 600)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Title
        title = QLabel('MediaSilo to Avid Marker Converter')
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # File selection group
        file_group = QGroupBox("File Selection")
        file_layout = QVBoxLayout()

        # Input file
        input_layout = QHBoxLayout()
        input_label = QLabel("Input CSV:")
        input_label.setMinimumWidth(100)
        self.input_line = QLineEdit()
        self.input_line.setReadOnly(True)
        self.input_line.setPlaceholderText("No file selected...")
        input_btn = QPushButton("Browse...")
        input_btn.clicked.connect(self.select_input_file)
        input_layout.addWidget(input_label)
        input_layout.addWidget(self.input_line)
        input_layout.addWidget(input_btn)
        file_layout.addLayout(input_layout)

        # Output file
        output_layout = QHBoxLayout()
        output_label = QLabel("Output TXT:")
        output_label.setMinimumWidth(100)
        self.output_line = QLineEdit()
        self.output_line.setReadOnly(True)
        self.output_line.setPlaceholderText("No file selected...")
        output_btn = QPushButton("Browse...")
        output_btn.clicked.connect(self.select_output_file)
        output_layout.addWidget(output_label)
        output_layout.addWidget(self.output_line)
        output_layout.addWidget(output_btn)
        file_layout.addLayout(output_layout)

        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)

        # Convert button
        self.convert_btn = QPushButton("Convert")
        self.convert_btn.setMinimumHeight(40)
        convert_font = QFont()
        convert_font.setPointSize(12)
        convert_font.setBold(True)
        self.convert_btn.setFont(convert_font)
        self.convert_btn.clicked.connect(self.start_conversion)
        self.convert_btn.setEnabled(False)
        main_layout.addWidget(self.convert_btn)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Log output
        log_group = QGroupBox("Conversion Log")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier", 9))
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

        # Clear log button
        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self.clear_log)
        main_layout.addWidget(clear_btn)

        self.log_message("Ready. Please select input and output files.")

    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select MediaSilo CSV File",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        if file_path:
            self.input_path = file_path
            self.input_line.setText(file_path)
            self.log_message(f"Input file selected: {file_path}")
            self.check_ready_to_convert()

    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Avid Marker File",
            "",
            "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            self.output_path = file_path
            self.output_line.setText(file_path)
            self.log_message(f"Output file selected: {file_path}")
            self.check_ready_to_convert()

    def check_ready_to_convert(self):
        if self.input_path and self.output_path:
            self.convert_btn.setEnabled(True)
        else:
            self.convert_btn.setEnabled(False)

    def validate_files(self):
        """
        Validate input/output files before conversion.

        Returns:
            Tuple of (success, error_message)
        """
        if not os.path.exists(self.input_path):
            return False, f"Input file does not exist:\n{self.input_path}"

        if not os.access(self.input_path, os.R_OK):
            return False, f"Cannot read input file:\n{self.input_path}\n\nCheck file permissions."

        output_dir = os.path.dirname(self.output_path)
        if output_dir and not os.path.exists(output_dir):
            return False, f"Output directory does not exist:\n{output_dir}"

        if output_dir and not os.access(output_dir, os.W_OK):
            return False, f"Cannot write to output directory:\n{output_dir}\n\nCheck folder permissions."

        return True, None

    def start_conversion(self):
        # Validate files before starting
        valid, error_msg = self.validate_files()
        if not valid:
            QMessageBox.critical(self, "Validation Error", error_msg)
            return

        # Check if worker is already running
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.warning(
                self,
                "Conversion In Progress",
                "A conversion is already running. Please wait for it to complete."
            )
            return

        # Disable button and show progress during conversion
        self.convert_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress

        self.log_message("\n" + "=" * 60)
        self.log_message("Starting conversion...")

        # Create and start worker thread
        self.worker = ConversionWorker(self.input_path, self.output_path)
        self.worker.progress.connect(self.log_message)
        self.worker.finished.connect(self.conversion_finished)
        self.worker.start()

    def conversion_finished(self, success, message):
        self.progress_bar.setVisible(False)
        self.convert_btn.setEnabled(True)
        self.worker = None  # Clear worker reference

        if success:
            self.log_message(f"\n✓ SUCCESS: {message}\n")
        else:
            self.log_message(f"\n✗ FAILED: {message}\n")

    def log_message(self, message):
        self.log_text.append(message)
        # Auto-scroll to bottom
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)

    def clear_log(self):
        self.log_text.clear()
        self.log_message("Log cleared. Ready for conversion.")


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look
    gui = MediaSiloConverterGUI()
    gui.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
