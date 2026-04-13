from PyQt6.QtWidgets import QWidget, QGridLayout, QSizePolicy, QFrame, QLabel, QComboBox, QPushButton
from ..data_saver import DataSaver

class SidePanel(QWidget):

    def __init__(self, dataSaver: DataSaver, parent=None):
        super().__init__(parent)
        self.callsigns = []
        self.dataSaver = dataSaver
        self.selected_callsigns = []
        self.selected_start_time = None
        self.selected_stop_time  = None
        self.get_current_time    = None  # callable set from MainUI: () -> str
        self.get_data_filename   = None  # callable set from MainUI: () -> str
        self.seek_to_time        = None  # callable set from MainUI: (time_str) -> None
        self.selected_task_number = None
        self._loaded_task_id = None
        self.tasks = ["Aircraft Request", #1
                      "Assume", #2
                      "Conflict Resolution", #3
                      "Entry Conditions", #4
                      "Entry Conflict Resolution", #5
                      "Entry Coordination", #6
                      "Exit Conditions", #7
                      "Exit Conflict Resolution", #8
                      "Exit Coordination", #9
                      "Non Conformance Resolution", #10
                      "Quality of Service", #11
                      "Return to Route", #12
                      "Transfer", #13
                      "Zone Conflict"] #14
        self._setup_ui()

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #
    def update_callsigns(self, callsigns=[]):
        self.callsigns = callsigns
        if self.callsign_combobox.view().isVisible():
            return
        current = self.callsign_combobox.currentText()
        self.callsign_combobox.clear()
        self.callsign_combobox.addItems(self.callsigns)
        index = self.callsign_combobox.findText(current)
        if index >= 0:
            self.callsign_combobox.setCurrentIndex(index)

    def refresh_task_dropdown(self):
        self.task_selector_combobox.blockSignals(True)
        self.task_selector_combobox.clear()
        self.task_selector_combobox.addItem("— select a task —")
        for task_id, task in sorted(self.dataSaver.data.items()):
            task_type_idx = task.get("task_type", 1)
            task_type_name = self.tasks[task_type_idx - 1] if 1 <= task_type_idx <= len(self.tasks) else "Unknown"
            self.task_selector_combobox.addItem(f"Task #{task_id}  —  {task_type_name}", userData=task_id)
        # Restore selection if the loaded task still exists
        if self._loaded_task_id is not None:
            for i in range(self.task_selector_combobox.count()):
                if self.task_selector_combobox.itemData(i) == self._loaded_task_id:
                    self.task_selector_combobox.setCurrentIndex(i)
                    break
            else:
                # Task was deleted — clear the form
                self._loaded_task_id = None
                self._clear_task()
        self.task_selector_combobox.blockSignals(False)

    # ------------------------------------------------------------------ #
    #  UI                                                                  #
    # ------------------------------------------------------------------ #

    def _setup_ui(self):
        #
        # Grid layout — columns:
        #   0: Task type / Start btn   1: Stop btn   2: Callsign / Add btn   3: Remove btn
        #   4: (stretching spacer)     5: Save / Clear / Delete (spans rows 0-4)
        #
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)

        # Row 0 — Loaded task selector (unchanged)
        lbl_select = QLabel("Loaded tasks:")
        self.task_selector_combobox = QComboBox()
        self.task_selector_combobox.addItem("— select a task —")
        self.task_selector_combobox.currentIndexChanged.connect(self._on_task_selected)
        grid.addWidget(lbl_select,                  0, 0)
        grid.addWidget(self.task_selector_combobox, 0, 1, 1, 3)  # span cols 1-3

        # Row 1 — Horizontal separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        grid.addWidget(separator, 1, 0, 1, 4)  # span cols 0-3

        # Row 2 — Task type dropdown (left, cols 0-1) | Callsign dropdown (right, cols 2-3)
        self.task_list_combobox = QComboBox()
        self.task_list_combobox.addItems(self.tasks)
        grid.addWidget(self.task_list_combobox, 2, 0, 1, 2)  # span cols 0-1

        self.callsign_combobox = QComboBox()
        grid.addWidget(self.callsign_combobox, 2, 2, 1, 2)  # span cols 2-3

        # Row 3 — Start/Stop time buttons | Add/Remove callsign buttons
        self.btn_set_start_time = QPushButton("Set Start Time")
        self.btn_set_start_time.clicked.connect(self._on_set_start_time)
        grid.addWidget(self.btn_set_start_time, 3, 0)

        self.btn_set_stop_time = QPushButton("Set Stop Time")
        self.btn_set_stop_time.clicked.connect(self._on_set_stop_time)
        grid.addWidget(self.btn_set_stop_time, 3, 1)

        self.btn_add_callsign = QPushButton("Add to Task")
        self.btn_add_callsign.clicked.connect(self._add_callsign)
        grid.addWidget(self.btn_add_callsign, 3, 2)

        self.btn_remove_callsign = QPushButton("Remove All")
        self.btn_remove_callsign.clicked.connect(self._clear_callsigns)
        grid.addWidget(self.btn_remove_callsign, 3, 3)

        # Row 4 — Time labels | Selected callsigns label
        self.lbl_start_time = QLabel("–")
        self.lbl_start_time.setStyleSheet("color: grey;")
        grid.addWidget(self.lbl_start_time, 4, 0)

        self.lbl_stop_time = QLabel("–")
        self.lbl_stop_time.setStyleSheet("color: grey;")
        grid.addWidget(self.lbl_stop_time, 4, 1)

        self.lbl_selected_callsigns = QLabel("–")
        grid.addWidget(self.lbl_selected_callsigns, 4, 2, 1, 2)  # span cols 2-3

        # Row 5 — Vertical spacer
        grid.setRowStretch(5, 1)

        # ── Spacer widths — adjust these values to taste ──────────────────
        SPACER_CONTENT_BUTTONS = 30   # col 4: between content and Save/Clear
        SPACER_CLEAR_DELETE    = 50   # col 7: between Clear and Delete
        SPACER_AFTER_DELETE    = 100   # col 9: trailing spacer after Delete
        # ──────────────────────────────────────────────────────────────────

        # Col 4 — Spacer between content and action buttons
        grid.setColumnMinimumWidth(4, SPACER_CONTENT_BUTTONS)

        # Col 5 — Save button, spans rows 0-4
        self.save_btn = QPushButton("Save Task")
        self.save_btn.setStyleSheet("background-color: green;")
        self.save_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_task)
        grid.addWidget(self.save_btn, 2, 5, 3, 1)  # span rows 2-4

        # Col 6 — Clear button, spans rows 2-4
        self.clear_btn = QPushButton("CLEAR")
        self.clear_btn.setStyleSheet("background-color: orange;")
        self.clear_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.clear_btn.clicked.connect(self._clear_task)
        grid.addWidget(self.clear_btn, 2, 6, 3, 1)  # span rows 2-4

        # Col 7 — Spacer between Clear and Delete
        grid.setColumnMinimumWidth(7, SPACER_CLEAR_DELETE)

        # Col 8 — Delete button, spans rows 2-4
        self.delete_btn = QPushButton("DELETE")
        self.delete_btn.setStyleSheet("background-color: red;")
        self.delete_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.delete_btn.clicked.connect(self._delete_task)
        grid.addWidget(self.delete_btn, 2, 8, 3, 1)  # span rows 2-4

        # Col 9 — Trailing spacer after Delete
        grid.setColumnMinimumWidth(9, SPACER_AFTER_DELETE)

    # ------------------------------------------------------------------ #
    #  Slots                                                               #
    # ------------------------------------------------------------------ #

    def _on_task_selected(self, index):
        task_id = self.task_selector_combobox.itemData(index)
        if task_id is None:
            return
        task = self.dataSaver.data.get(task_id)
        if task:
            self.load_task(task)

    def _on_set_start_time(self):
        if callable(self.get_current_time):
            self.selected_start_time = self.get_current_time()
            self.lbl_start_time.setText(self.selected_start_time)

    def _on_set_stop_time(self):
        if callable(self.get_current_time):
            self.selected_stop_time = self.get_current_time()
            self.lbl_stop_time.setText(self.selected_stop_time)

    def _add_callsign(self):
        callsign = self.callsign_combobox.currentText()
        if callsign and callsign not in self.selected_callsigns:
            self.selected_callsigns.append(callsign)
            self.lbl_selected_callsigns.setText(", ".join(self.selected_callsigns))
            self.save_btn.setEnabled(True)

    def _clear_callsigns(self):
        self.selected_callsigns.clear()
        self.save_btn.setEnabled(False)
        self.lbl_selected_callsigns.setText("-")

    def _save_task(self):
        if self._loaded_task_id:
            self.dataSaver.save_task(start=self.selected_start_time,
                                    end=self.selected_stop_time,
                                    callsigns=self.selected_callsigns,
                                    task_type=self.get_task_type_raw_value(), 
                                    task_id=self._loaded_task_id)
        else:
            self.dataSaver.save_task(start=self.selected_start_time,
                                    end=self.selected_stop_time,
                                    callsigns=self.selected_callsigns,
                                    task_type=self.get_task_type_raw_value())
        self._clear_task()

    def _delete_task(self):
        self.dataSaver.delete_task(self._loaded_task_id)

    def get_task_type_raw_value(self):
        selected_task = self.task_list_combobox.currentText()
        for i in range(len(self.tasks)):
            if self.tasks[i] == selected_task:
                return i+1
        return 0

    def load_task(self, task):
        self._loaded_task_id = task.get("id")
        if callable(self.seek_to_time):
            self.seek_to_time(task.get("start"))
        self.selected_start_time = task.get("start")
        self.lbl_start_time.setText(self.selected_start_time or "–")
        self.selected_stop_time = task.get("end")
        self.lbl_stop_time.setText(self.selected_stop_time or "–")
        self.selected_callsigns = list(task.get("callsigns") or [])
        self.lbl_selected_callsigns.setText(", ".join(self.selected_callsigns) if self.selected_callsigns else "–")
        self.save_btn.setEnabled(bool(self.selected_callsigns))
        task_type = task.get("task_type", 1)
        self.task_list_combobox.setCurrentIndex(task_type - 1)
        # Sync the dropdown selection
        self.task_selector_combobox.blockSignals(True)
        for i in range(self.task_selector_combobox.count()):
            if self.task_selector_combobox.itemData(i) == self._loaded_task_id:
                self.task_selector_combobox.setCurrentIndex(i)
                break
        self.task_selector_combobox.blockSignals(False)

    def _clear_task(self):
        self._loaded_task_id = None
        self.selected_start_time = None
        self.selected_stop_time  = None
        self.selected_callsigns.clear()
        self.lbl_start_time.setText("–")
        self.lbl_stop_time.setText("–")
        self.lbl_selected_callsigns.setText("–")
        self.save_btn.setEnabled(False)
        self.task_selector_combobox.blockSignals(True)
        self.task_selector_combobox.setCurrentIndex(0)
        self.task_selector_combobox.blockSignals(False)
