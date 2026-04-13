import json
import os
from pathlib import Path

class DataSaver:
    def __init__(self):
        self.current_tasks = []
        self.data = {}
        self.output_file_path = None
        self._next_id = 1
        self.on_task_saved = None    # callable set from outside; fired after each save
        self.on_task_deleted = None  # callable set from outside; fired after each delete
        print("Initialized")

    def get_json_string(self, start, end, callsigns, task_type, task_id):
        if task_id:
            task = {
                "id": task_id,
                "start": start,
                "end": end,
                "callsigns": list(callsigns),
                "task_type": task_type
            }
        else:
            task = {
                "id": self._next_id,
                "start": start,
                "end": end,
                "callsigns": list(callsigns),
                "task_type": task_type
            }
            self._next_id += 1
        
        return task

    def initialize_output_file(self, session_dir: Path):
        self.output_file_path = session_dir / "simulator" / f"{session_dir.name}_task_labelled.json"

        if os.path.exists(self.output_file_path):
            with open(self.output_file_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                self.data = {}
                for task in loaded:
                    if not task:
                        continue
                    self.data[task["id"]] = task
            self._next_id = (max(self.data.keys()) + 1) if self.data else 1
            print(f"Loaded existing output file: {self.output_file_path}")
        else:
            self.data = {}
            self._next_id = 1
            os.makedirs(os.path.dirname(self.output_file_path), exist_ok=True)
            with open(self.output_file_path, "w", encoding="utf-8") as f:
                json.dump([], f, indent=4)
            print(f"Created new output file: {self.output_file_path}")

    def save_task(self, start, end, callsigns, task_type, task_id=None):
        task = self.get_json_string(start, end, callsigns, task_type, task_id)
        self.data[task["id"]] = task
        self._write_to_file()
        if callable(self.on_task_saved):
            self.on_task_saved()

    def delete_task(self, task_id):
        if task_id is None or task_id not in self.data:
            return
        del self.data[task_id]
        self._write_to_file()
        if callable(self.on_task_deleted):
            self.on_task_deleted()

    def _write_to_file(self):
        if self.output_file_path:
            with open(self.output_file_path, "w", encoding="utf-8") as f:
                json.dump(list(self.data.values()), f, indent=4)
