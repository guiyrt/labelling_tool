
from enum import Enum
import uuid

class TaskLabel:
    
    def __init__(self, start, end, task, callsign):
        self.start = start
        self.end = end
        self.task_type = TaskType(task)
        self.callsign = callsign

class TaskType(Enum):
    INVALID = 0
    AIRCRAFT_REQUEST = 1
    CONFLICT_RESOLUTION = 2
    ENTRY_CONDITIONS = 3
    ENTRY_CONFLICT_RESOLUTION = 4
    ENTRY_COORDINATION = 5
    EXIT_CONDITIONS = 6
    EXIT_CONFLICT_RESOLUTION = 7
    EXIT_COORDINATION = 8
    NON_CONFORMANCE_RESOLUTION = 9
    QUALITY_OF_SERVICE = 10
    RETURN_TO_ROUTE = 11
    TRANSFER = 12
    ZONE_CONFLICT = 13

class Task:

    def __init__(self, start, end, task, callsigns, task_number):
        self.id = uuid.uuid4()
        self.start = start
        self.end = end
        self.task = task
        self.callsigns = callsigns
        self.task_number = task_number
