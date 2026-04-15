import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel,
                              QGraphicsView, QGraphicsScene, QGraphicsItem, QToolTip, QSizePolicy)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt6.QtCore import Qt, QUrl, QEvent, pyqtSignal, QRectF, QTimer
from PyQt6.QtGui import QPainter, QPen, QColor, QShortcut, QKeySequence

from ..path_finder import get_video_filepath, get_video_metadata_filepath


def ensure_seekable_video(original_path: Path) -> Path:
    """Checks if an indexed version exists. If not, performs a lossless remux."""
    indexed_path = original_path.with_name(f"{original_path.stem}_indexed.mkv")
    if indexed_path.exists():
        return indexed_path

    print("\n[INFO] Original video lacks a seek index. Running a lossless remux to enable fast timeline scrubbing (~2s)...")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(original_path), "-c", "copy", str(indexed_path)]
    try:
        subprocess.run(cmd, check=True)
        return indexed_path
    except subprocess.CalledProcessError:
        print("[WARNING] FFmpeg remux failed. Seeking may remain broken.")
        return original_path


class GazeOverlayItem(QGraphicsItem):
    """A custom QGraphicsItem that draws the gaze vector graphics on top of the video."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.gaze_x = 0.0
        self.gaze_y = 0.0
        self.radius = 20.0
        self.alpha = 0.0
        
        self.color_tracking = QColor(0, 255, 136) # #00ff88
        self.color_lost = QColor(255, 187, 0)     # #ffbb00

    def boundingRect(self):
        # Request redraws only for the area around the gaze to maximize 4K performance
        pad = self.radius + 30
        return QRectF(self.gaze_x - pad, self.gaze_y - pad, pad * 2, pad * 2)

    def set_gaze_state(self, x: float, y: float, r: float, alpha: float):
        self.prepareGeometryChange() # Tells Qt the bounding box is moving
        self.gaze_x = x
        self.gaze_y = y
        self.radius = r
        self.alpha = alpha
        self.update()

    def paint(self, painter, option, widget):
        if self.alpha <= 0.0:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        base_color = self.color_tracking if self.alpha == 1.0 else self.color_lost
        color = QColor(base_color.red(), base_color.green(), base_color.blue(), int(255 * self.alpha))
        
        pen = QPen(color)
        pen.setWidth(3)
        painter.setPen(pen)

        cx, cy = self.gaze_x, self.gaze_y
        r = self.radius
        painter.drawEllipse(int(cx - r), int(cy - r), int(r * 2), int(r * 2))

        ch = 15
        painter.drawLine(int(cx - ch), int(cy), int(cx + ch), int(cy))
        painter.drawLine(int(cx), int(cy - ch), int(cx), int(cy + ch))


class ZoomableVideoView(QGraphicsView):
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitInView(self.video_item, Qt.AspectRatioMode.KeepAspectRatio)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(1200, 800)
        self.setStyleSheet("background: black; border: none;")
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scene = QGraphicsScene(self)
        self.setScene(scene)

        # Video Item
        self.video_item = QGraphicsVideoItem()
        scene.addItem(self.video_item)
        self.video_item.nativeSizeChanged.connect(self._on_native_size_changed)

        # Gaze Overlay Item (Placed right on top of video)
        self.gaze_item = GazeOverlayItem(self.video_item)
        self.gaze_item.setZValue(1)

        self.grabGesture(Qt.GestureType.PinchGesture)

    def _on_native_size_changed(self, size):
        self.video_item.setSize(size)
        self.setSceneRect(self.video_item.boundingRect())
        self.fitInView(self.video_item, Qt.AspectRatioMode.KeepAspectRatio)

    def event(self, event):
        if event.type() == QEvent.Type.Gesture:
            pinch = event.gesture(Qt.GestureType.PinchGesture)
            if pinch:
                self.scale(pinch.scaleFactor(), pinch.scaleFactor())
            return True
        return super().event(event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.resetTransform()
        self.fitInView(self.video_item, Qt.AspectRatioMode.KeepAspectRatio)
        super().mouseDoubleClickEvent(event)


class MarkedSlider(QSlider):
    marker_clicked = pyqtSignal(dict)
    _HIT_RADIUS = 5 

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._markers = [] 
        self.setMouseTracking(True)

    def set_markers(self, markers):
        self._markers = markers
        self.update()

    def _task_at(self, x):
        for ratio, task in self._markers:
            if abs(int(ratio * self.width()) - x) <= self._HIT_RADIUS:
                return task
        return None

    def mouseMoveEvent(self, event):
        task = self._task_at(event.pos().x())
        if task:
            QToolTip.showText(event.globalPosition().toPoint(), f"Task #{task['id']}", self)
        else:
            QToolTip.hideText()
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            task = self._task_at(event.pos().x())
            if task:
                self.marker_clicked.emit(task)
                return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._markers: return
        painter = QPainter(self)
        pen = QPen(QColor(255, 140, 0, 220))
        pen.setWidth(2)
        painter.setPen(pen)
        w, h = self.width(), self.height()
        for ratio, _ in self._markers:
            x = int(ratio * w)
            painter.drawLine(x, 0, x, h)
        painter.end()


class VideoPlayer(QWidget):
    def __init__(self, filepath: str = None, parent=None):
        super().__init__(parent)
        self.isPlaying = False
        self._creation_time = None
        self._start_epoch_ms = None
        self._fps = 30.0
        self._pending_markers = None 
        
        # Gaze Physics State
        self.gaze_ts, self.gaze_x, self.gaze_y = None, None, None
        self.sm_x, self.sm_y = 0.0, 0.0
        self.last_raw_x, self.last_raw_y = 0.0, 0.0
        self.bubble_r = 20.0
        self.linger_frames = 0
        self.linger_max = 30 
        self.alpha = 0.0

        self._setup_ui()
        self._setup_player()

        # 60Hz Gaze Update Loop
        self.gaze_timer = QTimer(self)
        self.gaze_timer.timeout.connect(self._update_gaze_logic)

        if filepath:
            self.load(filepath)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.video_view = ZoomableVideoView()
        self.video_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.video_view, stretch=1)

        self.slider = MarkedSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.sliderMoved.connect(self._on_slider_moved)
        layout.addWidget(self.slider)

        controls = QHBoxLayout()

        self.btn_play  = QPushButton(text = ">")
        self.btn_pause = QPushButton(text = "||")
        self.btn_stop  = QPushButton(text = "x")
        self.btn_plus1s = QPushButton(text="+1s")
        self.btn_minus1s = QPushButton(text="-1s")
        self.btn_plus10s = QPushButton(text="+10s")
        self.btn_minus10s = QPushButton(text="-10s")
        
        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_abs_time = QLabel("–")
        self.lbl_abs_time.setStyleSheet("color: grey;")
        
        self.lbl_gaze_status = QLabel("GAZE: NO DATA")
        self.lbl_gaze_status.setStyleSheet("color: #444444; font-weight: bold; font-family: Consolas;")

        for btn in (self.btn_play, self.btn_pause, self.btn_stop):
            btn.setFixedWidth(40)
            controls.addWidget(btn)

        controls.addStretch(1)
        controls.addWidget(self.btn_minus10s)
        controls.addWidget(self.btn_minus1s)
        controls.addWidget(self.lbl_time)
        controls.addWidget(self.lbl_abs_time)
        controls.addWidget(self.lbl_gaze_status)
        controls.addWidget(self.btn_plus1s)
        controls.addWidget(self.btn_plus10s)
        controls.addStretch(8)

        self.btn_play.clicked.connect(self.play)
        self.btn_pause.clicked.connect(self.pause)
        self.btn_stop.clicked.connect(self.stop)
        self.btn_minus10s.clicked.connect(self.minus10Seconds)
        self.btn_minus1s.clicked.connect(self.minus1Second)
        self.btn_plus1s.clicked.connect(self.plus1Second)
        self.btn_plus10s.clicked.connect(self.plus10Seconds)
        
        QShortcut(QKeySequence("Left"), self, activated=lambda: self.seek_relative(-1))
        QShortcut(QKeySequence("Right"), self, activated=lambda: self.seek_relative(1))
        QShortcut(QKeySequence("Space"), self, activated=self.play_or_pause)

        layout.addLayout(controls)

    def _setup_player(self):
        self.player = QMediaPlayer()
        self.audio  = QAudioOutput()
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video_view.video_item)
        self.audio.setVolume(0.8)

        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.positionChanged.connect(self._on_position_changed)

    def load(self, session_path: Path):
        orig_video = get_video_filepath(session_path)
        seekable_video = ensure_seekable_video(orig_video)
        
        self.player.setSource(QUrl.fromLocalFile(str(seekable_video)))
        self._extract_metadata(get_video_metadata_filepath(session_path))

    def load_gaze_data(self, df: pd.DataFrame):
        df = df.sort_values("timestamp_ms")
        
        # Absolute bulletproof conversion to UNIX Epoch Milliseconds
        if pd.api.types.is_datetime64_any_dtype(df['timestamp_ms']):
            epoch = pd.Timestamp("1970-01-01", tz="UTC")
            # Localize to UTC if naive, otherwise convert
            if df['timestamp_ms'].dt.tz is None:
                dt_col = df['timestamp_ms'].dt.tz_localize("UTC")
            else:
                dt_col = df['timestamp_ms'].dt.tz_convert("UTC")
            self.gaze_ts = (dt_col - epoch).dt.total_seconds().to_numpy() * 1000.0
        else:
            self.gaze_ts = df['timestamp_ms'].to_numpy(dtype=np.float64)

        self.gaze_x = df['gaze_x_px'].to_numpy()
        self.gaze_y = df['gaze_y_px'].to_numpy()
        self.gaze_timer.start(16)

    def play(self):
        self.player.play()
        self.isPlaying = True

    def pause(self):
        self.player.pause()
        self.isPlaying = False

    def stop(self):
        self.player.stop()

    def play_or_pause(self):
        if self.isPlaying: self.pause()
        else: self.play()

    def current_time_ms(self) -> int:
        return self.player.position()

    def current_abs_time_str(self) -> str:
        ms = self.player.position()
        if self._creation_time and ms >= 0:
            abs_time = self._creation_time + timedelta(milliseconds=ms)
            return abs_time.strftime("%Y-%m-%d  %H:%M:%S.%f")[:-3]
        return "–"

    def set_task_markers(self, tasks):
        self._pending_markers = tasks
        self._apply_markers()

    def _apply_markers(self):
        if not self._pending_markers or not self._creation_time: return
        duration = self.player.duration()
        if duration <= 0: return

        task_list = list(self._pending_markers.values()) if isinstance(self._pending_markers, dict) else self._pending_markers
        creation = self._creation_time.replace(tzinfo=None)
        markers = []
        for task in task_list:
            start_str = task.get("start")
            if not start_str: continue
            try:
                start_dt = datetime.strptime(start_str, "%Y-%m-%d  %H:%M:%S.%f")
                offset_ms = (start_dt - creation).total_seconds() * 1000
                if 0 <= offset_ms <= duration:
                    markers.append((offset_ms / duration, task))
            except Exception: pass
        self.slider.set_markers(markers)
        self._pending_markers = None

    def seek_to_abs_time(self, time_str: str):
        if not self._creation_time or not time_str: return
        try:
            target_dt = datetime.strptime(time_str, "%Y-%m-%d  %H:%M:%S.%f")
            creation = self._creation_time.replace(tzinfo=None)
            offset_ms = int((target_dt - creation).total_seconds() * 1000)
            offset_ms = max(0, min(offset_ms, self.player.duration() if self.player.duration() > 0 else offset_ms))
            self.player.setPosition(offset_ms)
        except Exception: pass

    def seek_relative(self, seconds: float):
        delta_ms = int(seconds * 1000)
        new_pos = self.player.position() + delta_ms
        duration = self.player.duration()
        if duration > 0:
            new_pos = max(0, min(new_pos, duration))
        else:
            new_pos = max(0, new_pos)
        self.player.setPosition(new_pos)

    def minus1Second(self): self.seek_relative(-1)
    def minus10Seconds(self): self.seek_relative(-10)
    def plus1Second(self): self.seek_relative(1)
    def plus10Seconds(self): self.seek_relative(10)

    def _extract_metadata(self, metadata_file: Path):
        try:
            with open(metadata_file, "r") as fp:
                metadata = json.load(fp)
                
            # Safely parse ISO as UTC
            self._creation_time = datetime.fromisoformat(metadata["start_utc_iso"])
            if self._creation_time.tzinfo is None:
                self._creation_time = self._creation_time.replace(tzinfo=timezone.utc)
            
            # CRITICAL FIX: Ensure perfect Epoch mapping avoiding timezone drifts
            if "start_epoch_sec" in metadata:
                self._start_epoch_ms = float(metadata["start_epoch_sec"]) * 1000.0
            else:
                self._start_epoch_ms = self._creation_time.timestamp() * 1000.0

            self._fps = float(metadata.get("fps", 30.0))
        except Exception as e:
            print(f"Warning: Could not extract metadata from {metadata_file} ({e})")

    def _on_duration_changed(self, duration: int):
        if duration > 0:
            self.slider.setMaximum(duration)
        self._apply_markers()

    def _on_position_changed(self, position: int):
        if not self.slider.isSliderDown():
            self.slider.setValue(position)

        total_ms = max(0, self.player.duration())
        self.lbl_time.setText(f"{self._fmt(position)} / {self._fmt(total_ms)}")

        if self._creation_time and position >= 0:
            # We use tzinfo=None here purely for UI formatting
            abs_time = self._creation_time.replace(tzinfo=None) + timedelta(milliseconds=position)
            self.lbl_abs_time.setText(abs_time.strftime("%Y-%m-%d  %H:%M:%S.%f")[:-3])

    def _on_slider_moved(self, value: int):
        self.player.setPosition(value)
        self._update_gaze_logic()

    @staticmethod
    def _fmt(ms: int) -> str:
        if ms < 0: return "00:00"
        s = ms // 1000
        return f"{s // 60:02}:{s % 60:02}"

    def _update_gaze_logic(self):
        if self.gaze_ts is None or self._start_epoch_ms is None:
            return

        pos_ms = self.player.position()
        current_unix_ms = self._start_epoch_ms + pos_ms

        idx = np.searchsorted(self.gaze_ts, current_unix_ms)
        best_idx = idx
        if idx > 0:
            if idx == len(self.gaze_ts) or \
               abs(self.gaze_ts[idx - 1] - current_unix_ms) < abs(self.gaze_ts[idx] - current_unix_ms):
                best_idx = idx - 1

        valid = False
        gx, gy = 0.0, 0.0
        
        # Determine exactly why it might be failing for easy debugging
        status_text = "GAZE: LOST"
        
        if best_idx < len(self.gaze_ts):
            time_diff = abs(self.gaze_ts[best_idx] - current_unix_ms)
            gx_val = self.gaze_x[best_idx]
            gy_val = self.gaze_y[best_idx]
            
            # If the sync is off by more than 50ms, we explicitly show the gap to the user
            if time_diff > 50.0:
                status_text = f"GAZE: SYNC OFF ({int(time_diff)}ms)"
            elif pd.notna(gx_val) and pd.notna(gy_val):
                valid = True
                gx = float(gx_val)
                gy = float(gy_val)
            else:
                status_text = "GAZE: SENSOR BLINK (NaN)"

        if valid:
            if self.alpha == 0.0:
                self.sm_x, self.sm_y = gx, gy
            else:
                self.sm_x += (gx - self.sm_x) * 0.4
                self.sm_y += (gy - self.sm_y) * 0.4

            dist = np.hypot(gx - self.last_raw_x, gy - self.last_raw_y)
            if dist < 50.0: 
                self.bubble_r = min(100.0, self.bubble_r + 4.0)
            else:
                self.bubble_r = max(20.0, self.bubble_r - 10.0)

            self.last_raw_x = gx
            self.last_raw_y = gy
            self.linger_frames = self.linger_max
            self.alpha = 1.0
            
            self.lbl_gaze_status.setText(f"GAZE: X:{int(self.sm_x):04d} Y:{int(self.sm_y):04d}")
            self.lbl_gaze_status.setStyleSheet("color: #00ff88; font-weight: bold; font-family: Consolas;")
        else:
            self.linger_frames = max(0, self.linger_frames - 1)
            self.alpha = self.linger_frames / float(self.linger_max)
            
            self.lbl_gaze_status.setText(status_text)
            self.lbl_gaze_status.setStyleSheet("color: #ffbb00; font-weight: bold; font-family: Consolas;")

        self.video_view.gaze_item.set_gaze_state(self.sm_x, self.sm_y, self.bubble_r, self.alpha)