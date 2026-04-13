
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel,
                              QGraphicsView, QGraphicsScene, QToolTip, QSizePolicy)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt6.QtCore import Qt, QUrl, QEvent, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QColor, QShortcut, QKeySequence

from ..path_finder import get_video_filepath, get_video_metadata_filepath


class ZoomableVideoView(QGraphicsView):
    """QGraphicsView wrapper around QGraphicsVideoItem that supports pinch-to-zoom."""

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

        self.video_item = QGraphicsVideoItem()
        scene.addItem(self.video_item)
        self.video_item.nativeSizeChanged.connect(self._on_native_size_changed)

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
        # Ctrl+scroll as an alternative zoom trigger
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event):
        # Double-click resets zoom and re-fits the video
        self.resetTransform()
        self.fitInView(self.video_item, Qt.AspectRatioMode.KeepAspectRatio)
        super().mouseDoubleClickEvent(event)


class MarkedSlider(QSlider):
    """QSlider that draws vertical tick marks and supports hover/click on markers."""

    marker_clicked = pyqtSignal(dict)
    _HIT_RADIUS = 5  # px

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._markers = []  # list of (ratio, task_dict)
        self.setMouseTracking(True)

    def set_markers(self, markers):
        """markers: list of (ratio, task_dict)"""
        self._markers = markers
        self.update()

    def _task_at(self, x):
        """Return the task_dict whose marker is within _HIT_RADIUS of x, or None."""
        for ratio, task in self._markers:
            if abs(int(ratio * self.width()) - x) <= self._HIT_RADIUS:
                return task
        return None

    def mouseMoveEvent(self, event):
        task = self._task_at(event.pos().x())
        
        if task:
            QToolTip.showText(event.globalPosition().toPoint(),
                              f"Task #{task['id']}", self)
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
        if not self._markers:
            return
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
    """
    A self-contained video player widget using QMediaPlayer.
    Can be embedded in any QWidget or QMainWindow.

    Usage:
        player = VideoPlayer()
        layout.addWidget(player)
        player.load("path/to/video.mkv")
    """

    def __init__(self, filepath: str = None, parent=None):
        super().__init__(parent)
        self._creation_time = None
        self._fps = 30.0
        self._pending_markers = None  # tasks to apply once duration is known
        self._setup_ui()
        self._setup_player()

        if filepath:
            self.load(filepath)

    # ------------------------------------------------------------------ #
    #  UI                                                                  #
    # ------------------------------------------------------------------ #

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Video surface
        self.video_view = ZoomableVideoView()
        self.video_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self.video_view, stretch=1)

        # Seek slider
        self.slider = MarkedSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.sliderMoved.connect(self._on_slider_moved)
        layout.addWidget(self.slider)

        # Controls row
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

        for btn in (self.btn_play, self.btn_pause, self.btn_stop):
            btn.setFixedWidth(40)
            controls.addWidget(btn)

        controls.addStretch(1)
        controls.addWidget(self.btn_minus10s)
        controls.addWidget(self.btn_minus1s)
        controls.addWidget(self.lbl_time)
        controls.addWidget(self.lbl_abs_time)
        controls.addWidget(self.btn_plus1s)
        controls.addWidget(self.btn_plus10s)
        controls.addStretch(8)

        self.btn_play.clicked.connect(self.play)
        self.btn_pause.clicked.connect(self.pause)
        self.btn_stop.clicked.connect(self.stop)
        self.btn_minus10s.clicked.connect(self.minus10Seconds)
        self.btn_minus1s.clicked.connect(self.minus1Second)
        QShortcut(QKeySequence("Left"), self, activated=lambda: self.seek_relative(-1))
        QShortcut(QKeySequence("s"), self, activated=lambda: self.seek_relative(-1))
        QShortcut(QKeySequence("a"), self, activated=lambda: self.seek_relative(-10))
        self.btn_plus1s.clicked.connect(self.plus1Second)
        QShortcut(QKeySequence("Right"), self, activated=lambda: self.seek_relative(1))
        QShortcut(QKeySequence("d"), self, activated=lambda: self.seek_relative(1))
        QShortcut(QKeySequence("f"), self, activated=lambda: self.seek_relative(10))
        self.btn_plus10s.clicked.connect(self.plus10Seconds)
        QShortcut(QKeySequence("Space"), self, activated=lambda: self.play_or_pause())
        layout.addLayout(controls)

    # ------------------------------------------------------------------ #
    #  Player                                                              #
    # ------------------------------------------------------------------ #

    def _setup_player(self):
        self.player = QMediaPlayer()
        self.audio  = QAudioOutput()
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video_view.video_item)
        self.audio.setVolume(0.8)

        # Signals
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.positionChanged.connect(self._on_position_changed)

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def load(self, session_path: Path):
        self.player.setSource(QUrl.fromLocalFile(str(get_video_filepath(session_path))))
        self._extract_metadata(get_video_metadata_filepath(session_path))

    def play(self):
        self.player.play()
        self.isPlaying = True

    def pause(self):
        self.player.pause()
        self.isPlaying = False

    def stop(self):
        self.player.stop()

    def play_or_pause(self):
        if self.isPlaying:
            self.pause()
        else:
            self.play()

    def current_time_ms(self) -> int:
        return self.player.position()

    def current_abs_time_str(self) -> str:
        ms = self.player.position()
        if self._creation_time and ms >= 0:
            abs_time = self._creation_time + timedelta(milliseconds=ms)
            return abs_time.strftime("%Y-%m-%d  %H:%M:%S.%f")[:-3]
        return "–"
    
    def set_task_markers(self, tasks):
        """Draw a tick on the slider for each task's start time."""
        self._pending_markers = tasks
        self._apply_markers()

    def _apply_markers(self):
        if not self._pending_markers or not self._creation_time:
            return
        duration = self.player.duration()
        if duration <= 0:
            return  # wait for _on_duration_changed to retry

        task_list = list(self._pending_markers.values()) if isinstance(self._pending_markers, dict) else self._pending_markers
        creation = self._creation_time.replace(tzinfo=None)
        markers = []
        for task in task_list:
            start_str = task.get("start")
            if not start_str:
                continue
            try:
                start_dt = datetime.strptime(start_str, "%Y-%m-%d  %H:%M:%S.%f")
                offset_ms = (start_dt - creation).total_seconds() * 1000
                if 0 <= offset_ms <= duration:
                    markers.append((offset_ms / duration, task))
            except Exception:
                pass
        self.slider.set_markers(markers)
        self._pending_markers = None

    def seek_to_abs_time(self, time_str: str):
        """Seek to an absolute timestamp string (format: 'YYYY-MM-DD  HH:MM:SS.fff')."""
        if not self._creation_time or not time_str:
            return
        try:
            target_dt = datetime.strptime(time_str, "%Y-%m-%d  %H:%M:%S.%f")
            creation = self._creation_time.replace(tzinfo=None)
            offset_ms = int((target_dt - creation).total_seconds() * 1000)
            offset_ms = max(0, min(offset_ms, self.player.duration()))
            self.player.setPosition(offset_ms)
        except Exception:
            pass

    def seek_relative(self, seconds: float):
        """Shift playback position by +/− seconds."""
        delta_ms = int(seconds * 1000)

        new_pos = self.player.position() + delta_ms

        # Clamp to valid range
        new_pos = max(0, min(new_pos, self.player.duration()))

        self.player.setPosition(new_pos)

    def minus1Second(self):
        self.seek_relative(-1)
    
    def minus10Seconds(self):
        self.seek_relative(-10)
    
    def plus1Second(self):
        self.seek_relative(1)

    def plus10Seconds(self):
        self.seek_relative(10)

    # ------------------------------------------------------------------ #
    #  Metadata                                                            #
    # ------------------------------------------------------------------ #
        
    def _extract_metadata(self, metadata_file: Path):
        try:
            with open(metadata_file, "r") as fp:
                metadata = json.load(fp)
            
            self._creation_time = datetime.fromtimestamp(float(metadata["start_epoch_sec"]), timezone.utc)
            self._fps = float(metadata["fps"])

        except Exception:
            raise ValueError("Metadata could not be extracted.")
            

    # ------------------------------------------------------------------ #
    #  Internal updates                                                    #
    # ------------------------------------------------------------------ #

    def _on_duration_changed(self, duration: int):
        self.slider.setMaximum(duration)
        self._apply_markers()  # flush any markers that arrived before duration was known

    def _on_position_changed(self, position: int):
        self.slider.setValue(position)

        total_ms = self.player.duration()
        self.lbl_time.setText(f"{self._fmt(position)} / {self._fmt(total_ms)}")

        if self._creation_time and position >= 0:
            abs_time = self._creation_time + timedelta(milliseconds=position)
            self.lbl_abs_time.setText(abs_time.strftime("%Y-%m-%d  %H:%M:%S.%f")[:-3])

    def _on_slider_moved(self, value: int):
        self.player.setPosition(value)

    @staticmethod
    def _fmt(ms: int) -> str:
        if ms < 0:
            return "00:00"
        s = ms // 1000
        return f"{s // 60:02}:{s % 60:02}"
    