import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QFileDialog
)
from pathlib import Path

from ..path_finder import get_video_filepath, get_parquet_filepath

class FileControls(QWidget):
    """
    A toolbar with two file-picker buttons:
      - Load Video  → emits the selected filepath via on_video_loaded(path)
      - Load Data   → loads a parquet file into a DataFrame via on_data_loaded(df)

    Usage:
        self.file_controls = FileControls()
        self.file_controls.on_video_loaded = lambda path: self.player.load(path)
        self.file_controls.on_data_loaded  = lambda df:   self.handle_data(df)
        layout.addWidget(self.file_controls)
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Callbacks — assign these from outside
        self.on_video_loaded = None   # callable(filepath: str)
        self.on_data_loaded  = None   # callable(df: pd.DataFrame)

        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Single Session button
        self.btn_session = QPushButton("Load Session")
        self.btn_session.clicked.connect(self._pick_session)
        layout.addWidget(self.btn_session)

        # Status label
        self.lbl_status = QLabel("No session loaded.")
        self.lbl_status.setStyleSheet("color: grey;")
        layout.addWidget(self.lbl_status)

        layout.addStretch()

    def _pick_session(self):
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Session Folder",
            ""
        )
        
        if not folder_path:
            return  # User canceled the dialog

        session_dir = Path(folder_path)
        sim_dir = session_dir / "simulator"
        vid_dir = session_dir / "videoRecordings"

        # Validate subfolders exist
        if not sim_dir.is_dir() or not vid_dir.is_dir():
            self._set_error("Invalid session: Missing 'simulator' or 'videoRecordings' folder.")
            return

        # Validate contents
        if not list(sim_dir.glob("*.parquet")):
            self._set_error("Invalid session: No .parquet files found in 'simulator'.")
            return

        video_exts = {".mkv", ".mp4", ".avi", ".mov"}
        if not any(f for f in vid_dir.iterdir() if f.is_file() and f.suffix.lower() in video_exts):
            self._set_error("Invalid session: No video files found in 'videoRecordings'.")
            return

        try:
            # Fire callbacks
            if callable(self.on_video_loaded):
                self.on_video_loaded(session_dir)
                
            if callable(self.on_data_loaded):
                self.on_data_loaded(session_dir)

            # Update UI on success
            self.lbl_status.setText(f"Loaded: {session_dir.name}")
            self.lbl_status.setStyleSheet("color: green;")
            
        except Exception as e:
            self._set_error(f"Error reading data: {e}")

    def _set_error(self, message: str):
        """Helper to display error messages."""
        self.lbl_status.setText(message)
        self.lbl_status.setStyleSheet("color: red;")