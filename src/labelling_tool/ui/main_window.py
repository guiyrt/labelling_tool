from datetime import timedelta
from pathlib import Path
import pandas as pd

from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout

from ..ui.video_player import VideoPlayer
from ..ui.file_loader import FileControls
from ..ui.task import SidePanel
from ..data_saver import DataSaver
from ..path_finder import get_parquet_filepath, get_gaze_parquet_filepath

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.dataSaver = DataSaver()
        self.setWindowTitle("AWARE Labelling Tool")
        self.df = None
        self.data_filename = None
        self._last_filter_second = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # File IO
        top = QHBoxLayout()
        self.file_controls = FileControls()
        self.file_controls.on_video_loaded = self._on_video_loaded
        self.file_controls.on_data_loaded  = self._on_data_loaded
        top.addWidget(self.file_controls)
        top.addStretch()
        layout.addWidget(self.file_controls, stretch=0)

        # Video player
        self.player = VideoPlayer()
        self.player.player.positionChanged.connect(self._on_video_position_changed)
        layout.addWidget(self.player, stretch=1)

        # Bottom row
        bottom = QHBoxLayout()
        self.side_panel = SidePanel(self.dataSaver)
        self.side_panel.get_current_time  = self.player.current_abs_time_str
        self.side_panel.get_data_filename = lambda: self.data_filename
        self.side_panel.seek_to_time      = self.player.seek_to_abs_time
        self.player.slider.marker_clicked.connect(self.side_panel.load_task)
        self.dataSaver.on_task_saved = self._on_tasks_changed
        self.dataSaver.on_task_deleted = self._on_tasks_changed
        bottom.addWidget(self.side_panel)

        layout.addLayout(bottom, stretch=0)

    def _on_tasks_changed(self):
        self.player.set_task_markers(self.dataSaver.data)
        self.side_panel.refresh_task_dropdown()

    def _on_video_loaded(self, session_dir: Path):
        self.player.load(session_dir)
        self.player.play()
        if self.dataSaver.data:
            self.player.set_task_markers(self.dataSaver.data)

    def _on_data_loaded(self, session_dir: Path):
        # 1. Load Simulator Data
        self.data_filename = get_parquet_filepath(session_dir)
        self.df = pd.read_parquet(self.data_filename)
        print(f"Loaded simulator dataframe: {self.df.shape}")
        
        # 2. Load Gaze Data (if exists)
        gaze_file = get_gaze_parquet_filepath(session_dir)
        if gaze_file.exists():
            print(f"Loading gaze data from {gaze_file.name}...")
            gaze_df = pd.read_parquet(gaze_file)
            self.player.load_gaze_data(gaze_df)
        else:
            print(f"No gaze data found at {gaze_file}")

        self.dataSaver.initialize_output_file(session_dir)
        if self.dataSaver.data:
            self.player.set_task_markers(self.dataSaver.data)
            self.side_panel.refresh_task_dropdown()
        self.side_panel.update_callsigns(callsigns=list(self.df.callsign.unique()))

    def _on_video_position_changed(self, position: int):
        if self.df is None or not self.player._creation_time:
            return

        abs_time = self.player._creation_time + timedelta(milliseconds=position)
        current_second = abs_time.replace(microsecond=0)
        if current_second == self._last_filter_second:
            return
        self._last_filter_second = current_second
        window = timedelta(minutes=2.5)

        mask = (
            (self.df["timestamp"] >= abs_time - window) &
            (self.df["timestamp"] <= abs_time + window)
        )
        filtered = sorted(
            callsign
            for callsign in self.df.loc[mask, "callsign"].unique()
            if not callsign.startswith("TrackNumber")
        )

        self.side_panel.update_callsigns(callsigns=filtered)