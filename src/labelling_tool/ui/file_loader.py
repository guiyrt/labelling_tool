from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QFileDialog
)
from pathlib import Path

class FileControls(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.on_video_loaded = None   
        self.on_data_loaded  = None   
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.btn_session = QPushButton("Load Session")
        self.btn_session.clicked.connect(self._pick_session)
        layout.addWidget(self.btn_session)

        self.lbl_status = QLabel("No session loaded.")
        self.lbl_status.setStyleSheet("color: grey;")
        layout.addWidget(self.lbl_status)
        layout.addStretch()

    def _pick_session(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Session Folder", "")
        if not folder_path:
            return  

        session_dir = Path(folder_path)
        asd_dir = session_dir / "asdEvents"
        vid_dir = session_dir / "videoRecordings"
        et_dir = session_dir / "ET"

        if not asd_dir.is_dir() or not vid_dir.is_dir() or not et_dir.is_dir():
            self._set_error("Invalid session: Missing 'asd_events' or 'videoRecordings' folder.")
            return

        if not list(asd_dir.glob("*.parquet")):
            self._set_error("Invalid session: No .parquet files found in 'asd_events'.")
            return
        
        if not list(asd_dir.glob("*.parquet")):
            self._set_error("Invalid session: No .parquet files found in 'asd_events'.")
            return

        video_exts = {".mkv", ".mp4", ".avi", ".mov"}
        if not any(f for f in vid_dir.iterdir() if f.is_file() and f.suffix.lower() in video_exts):
            self._set_error("Invalid session: No video files found in 'videoRecordings'.")
            return

        try:
            if callable(self.on_video_loaded):
                self.on_video_loaded(session_dir)
                
            if callable(self.on_data_loaded):
                self.on_data_loaded(session_dir)

            self.lbl_status.setText(f"Loaded: {session_dir.name}")
            self.lbl_status.setStyleSheet("color: green;")
            
        except Exception as e:
            self._set_error(f"Error reading data: {e}")

    def _set_error(self, message: str):
        self.lbl_status.setText(message)
        self.lbl_status.setStyleSheet("color: red;")