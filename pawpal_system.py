"""PawPal+ core domain model (Owner, Pet, Task) and scheduling algorithms (Scheduler)."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import date as date_cls
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

PRIORITIES = ("High", "Medium", "Low")
PRIORITY_RANK = {"High": 0, "Medium": 1, "Low": 2}
FREQUENCIES = ("Once", "Daily", "Weekly")
STATUSES = ("Pending", "Completed")
RECURRENCE_DELTAS = {"Daily": timedelta(days=1), "Weekly": timedelta(weeks=1)}

DATE_FMT = "%Y-%m-%d"
TIME_FMT = "%H:%M"
MINUTES_PER_DAY = 24 * 60


def _new_id() -> str:
    """Return a short unique identifier."""
    return uuid.uuid4().hex[:8]


def time_to_minutes(value: str) -> int:
    """Convert an 'HH:MM' string to minutes since midnight."""
    parsed = datetime.strptime(value, TIME_FMT)
    return parsed.hour * 60 + parsed.minute


def minutes_to_time(minutes: int) -> str:
    """Convert minutes since midnight to an 'HH:MM' string (1440 renders as '24:00')."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def today_str() -> str:
    """Return today's date as 'YYYY-MM-DD'."""
    return date_cls.today().strftime(DATE_FMT)


# --------------------------------------------------------------------------- #
# Task
# --------------------------------------------------------------------------- #
class Task:
    """A single pet-care activity scheduled at a specific date and time."""

    def __init__(
        self,
        description: str,
        time: str,
        date: str,
        category: str = "General",
        priority: str = "Medium",
        duration_mins: int = 15,
        status: str = "Pending",
        frequency: str = "Once",
        id: Optional[str] = None,
        pet_id: Optional[str] = None,
    ) -> None:
        """Create a task, validating time/date formats, priority, frequency and duration."""
        if not str(description).strip():
            raise ValueError("Task description cannot be empty.")
        try:
            time_to_minutes(time)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid time {time!r}; expected 'HH:MM' (24-hour).") from None
        try:
            datetime.strptime(date, DATE_FMT)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid date {date!r}; expected 'YYYY-MM-DD'.") from None
        if priority not in PRIORITIES:
            raise ValueError(f"Invalid priority {priority!r}; choose from {PRIORITIES}.")
        if frequency not in FREQUENCIES:
            raise ValueError(f"Invalid frequency {frequency!r}; choose from {FREQUENCIES}.")
        if status not in STATUSES:
            raise ValueError(f"Invalid status {status!r}; choose from {STATUSES}.")
        if int(duration_mins) <= 0:
            raise ValueError("duration_mins must be a positive integer.")

        self.id = id or _new_id()
        self.description = str(description).strip()
        self.time = time
        self.date = date
        self.category = category
        self.priority = priority
        self.duration_mins = int(duration_mins)
        self.status = status
        self.frequency = frequency
        self.pet_id = pet_id

    @property
    def start_minutes(self) -> int:
        """Return the start time as minutes since midnight."""
        return time_to_minutes(self.time)

    @property
    def end_minutes(self) -> int:
        """Return the end time as minutes since midnight, clamped to the end of the day."""
        return min(self.start_minutes + self.duration_mins, MINUTES_PER_DAY)

    @property
    def end_time(self) -> str:
        """Return the end time as an 'HH:MM' string."""
        return minutes_to_time(self.end_minutes)

    @property
    def is_complete(self) -> bool:
        """Return True when the task has been completed."""
        return self.status == "Completed"

    def mark_complete(self) -> "Task":
        """Mark this task as completed and return it."""
        self.status = "Completed"
        return self

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the task into a JSON-friendly dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "time": self.time,
            "date": self.date,
            "category": self.category,
            "priority": self.priority,
            "duration_mins": self.duration_mins,
            "status": self.status,
            "frequency": self.frequency,
            "pet_id": self.pet_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Rebuild a task from a dictionary produced by to_dict()."""
        return cls(
            description=data["description"],
            time=data["time"],
            date=data["date"],
            category=data.get("category", "General"),
            priority=data.get("priority", "Medium"),
            duration_mins=data.get("duration_mins", 15),
            status=data.get("status", "Pending"),
            frequency=data.get("frequency", "Once"),
            id=data.get("id"),
            pet_id=data.get("pet_id"),
        )

    def __repr__(self) -> str:
        """Return a compact debugging representation."""
        return (
            f"Task({self.description!r}, {self.date} {self.time}, "
            f"{self.priority}, {self.duration_mins}m, {self.status})"
        )


# --------------------------------------------------------------------------- #
# Pet
# --------------------------------------------------------------------------- #
class Pet:
    """A pet that owns a list of care tasks."""

    def __init__(
        self,
        name: str,
        species: str,
        breed: str = "Unknown",
        age: int = 0,
        id: Optional[str] = None,
        tasks: Optional[List[Task]] = None,
    ) -> None:
        """Create a pet and attach any initial tasks."""
        if not str(name).strip():
            raise ValueError("Pet name cannot be empty.")
        self.id = id or _new_id()
        self.name = str(name).strip()
        self.species = species
        self.breed = breed
        self.age = age
        self.tasks: List[Task] = []
        for task in tasks or []:
            self.add_task(task)

    def add_task(self, task: Task) -> Task:
        """Attach a task to this pet and return it."""
        if any(existing.id == task.id for existing in self.tasks):
            raise ValueError(f"Task id {task.id!r} already exists for {self.name}.")
        task.pet_id = self.id
        self.tasks.append(task)
        return task

    def remove_task(self, task_id: str) -> bool:
        """Remove a task by id; return True if something was removed."""
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.id != task_id]
        return len(self.tasks) < before

    def get_tasks(self, status: Optional[str] = None) -> List[Task]:
        """Return a copy of this pet's tasks, optionally filtered by status."""
        if status is None:
            return list(self.tasks)
        return [t for t in self.tasks if t.status.lower() == status.lower()]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the pet and its tasks into a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "species": self.species,
            "breed": self.breed,
            "age": self.age,
            "tasks": [t.to_dict() for t in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pet":
        """Rebuild a pet (and its tasks) from a dictionary produced by to_dict()."""
        pet = cls(
            name=data["name"],
            species=data.get("species", "Other"),
            breed=data.get("breed", "Unknown"),
            age=data.get("age", 0),
            id=data.get("id"),
        )
        for task_data in data.get("tasks", []):
            pet.add_task(Task.from_dict(task_data))
        return pet

    def __repr__(self) -> str:
        """Return a compact debugging representation."""
        return f"Pet({self.name!r}, {self.species}, {len(self.tasks)} tasks)"


# --------------------------------------------------------------------------- #
# Owner
# --------------------------------------------------------------------------- #
class Owner:
    """A pet owner who manages one or more pets."""

    def __init__(
        self,
        name: str,
        email: str = "",
        id: Optional[str] = None,
        pets: Optional[List[Pet]] = None,
    ) -> None:
        """Create an owner and attach any initial pets."""
        if not str(name).strip():
            raise ValueError("Owner name cannot be empty.")
        self.id = id or _new_id()
        self.name = str(name).strip()
        self.email = email
        self.pets: List[Pet] = []
        for pet in pets or []:
            self.add_pet(pet)

    def add_pet(self, pet: Pet) -> Pet:
        """Register a pet with this owner and return it."""
        if any(existing.id == pet.id for existing in self.pets):
            raise ValueError(f"Pet id {pet.id!r} is already registered.")
        self.pets.append(pet)
        return pet

    def remove_pet(self, pet_id: str) -> bool:
        """Remove a pet by id; return True if something was removed."""
        before = len(self.pets)
        self.pets = [p for p in self.pets if p.id != pet_id]
        return len(self.pets) < before

    def get_pet(self, ref: str) -> Optional[Pet]:
        """Find a pet by id or (case-insensitive) name."""
        for pet in self.pets:
            if pet.id == ref or pet.name.lower() == str(ref).lower():
                return pet
        return None

    def get_all_tasks(self) -> List[Task]:
        """Return every task across all pets as one flat list."""
        return [task for pet in self.pets for task in pet.tasks]

    def find_task(self, task_id: str) -> Tuple[Optional[Pet], Optional[Task]]:
        """Locate a task by id and return its (pet, task), or (None, None)."""
        for pet in self.pets:
            for task in pet.tasks:
                if task.id == task_id:
                    return pet, task
        return None, None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the owner, pets and tasks into a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "pets": [p.to_dict() for p in self.pets],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Owner":
        """Rebuild an owner (and everything beneath it) from a dictionary."""
        owner = cls(name=data["name"], email=data.get("email", ""), id=data.get("id"))
        for pet_data in data.get("pets", []):
            owner.add_pet(Pet.from_dict(pet_data))
        return owner

    def save_to_json(self, filepath: str) -> None:
        """Persist this owner and all nested data to a JSON file."""
        JsonPersistence.save(self, filepath)

    @classmethod
    def load_from_json(cls, filepath: str) -> "Owner":
        """Load an owner and all nested data from a JSON file."""
        return JsonPersistence.load(filepath)

    def __repr__(self) -> str:
        """Return a compact debugging representation."""
        return f"Owner({self.name!r}, {len(self.pets)} pets)"


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
class JsonPersistence:
    """Reads and writes an Owner object graph as a versioned JSON document."""

    SCHEMA_VERSION = 1

    @staticmethod
    def save(owner: Owner, filepath: str) -> None:
        """Write the owner to filepath atomically (temp file + rename)."""
        payload = {"version": JsonPersistence.SCHEMA_VERSION, "owner": owner.to_dict()}
        directory = os.path.dirname(os.path.abspath(filepath))
        os.makedirs(directory, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            os.replace(tmp_path, filepath)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    @staticmethod
    def load(filepath: str) -> Owner:
        """Read an owner from filepath; raises FileNotFoundError or ValueError on bad input."""
        with open(filepath, "r", encoding="utf-8") as handle:
            try:
                payload = json.load(handle)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{filepath} is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{filepath} does not contain a JSON object.")
        owner_data = payload.get("owner", payload)
        try:
            return Owner.from_dict(owner_data)
        except KeyError as exc:
            raise ValueError(f"{filepath} is missing required field {exc}.") from exc


# --------------------------------------------------------------------------- #
# Scheduler
# --------------------------------------------------------------------------- #
class Scheduler:
    """The scheduling brain: sorting, filtering, conflicts, recurrence and slot finding."""

    def __init__(self, owner: Owner) -> None:
        """Bind the scheduler to an owner whose pets/tasks it will analyse."""
        self.owner = owner

    # ---- helpers --------------------------------------------------------- #
    def pet_name_for(self, task: Task) -> str:
        """Return the name of the pet that owns a task."""
        for pet in self.owner.pets:
            if pet.id == task.pet_id:
                return pet.name
        return "Unknown"

    def _tasks_for(self, tasks: Optional[List[Task]]) -> List[Task]:
        """Return the given task list, or every owner task when None."""
        return list(tasks) if tasks is not None else self.owner.get_all_tasks()

    # ---- feature 1: sorting --------------------------------------------- #
    def sort_tasks(self, tasks: Optional[List[Task]] = None, by: str = "priority") -> List[Task]:
        """Sort tasks by priority then date/time (by='priority') or by date/time only (by='time')."""
        if by not in ("priority", "time"):
            raise ValueError("by must be 'priority' or 'time'.")

        def key(task: Task):
            """Build the sort key for one task."""
            when = (task.date, task.time)
            if by == "time":
                return (*when, PRIORITY_RANK[task.priority], task.description)
            return (PRIORITY_RANK[task.priority], *when, task.description)

        return sorted(self._tasks_for(tasks), key=key)

    # ---- feature 2: filtering ------------------------------------------- #
    def filter_tasks(
        self,
        tasks: Optional[List[Task]] = None,
        status: Optional[str] = None,
        pet: Optional[str] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
        date: Optional[str] = None,
    ) -> List[Task]:
        """Return tasks matching every supplied criterion (pet may be an id or a name)."""
        result = self._tasks_for(tasks)
        if status is not None:
            result = [t for t in result if t.status.lower() == status.lower()]
        if pet is not None:
            target = self.owner.get_pet(pet)
            target_id = target.id if target else None
            result = [t for t in result if target_id is not None and t.pet_id == target_id]
        if category is not None:
            result = [t for t in result if t.category.lower() == category.lower()]
        if priority is not None:
            result = [t for t in result if t.priority.lower() == priority.lower()]
        if date is not None:
            result = [t for t in result if t.date == date]
        return result

    # ---- feature 3: conflict detection ---------------------------------- #
    def find_conflict_pairs(
        self, date: Optional[str] = None, include_completed: bool = False
    ) -> List[Tuple[Task, Task, int]]:
        """Return (task_a, task_b, overlap_minutes) for every overlapping pair on the same date."""
        candidates = self.owner.get_all_tasks()
        if not include_completed:
            candidates = [t for t in candidates if not t.is_complete]
        if date is not None:
            candidates = [t for t in candidates if t.date == date]

        by_day: Dict[str, List[Task]] = {}
        for task in candidates:
            by_day.setdefault(task.date, []).append(task)

        pairs: List[Tuple[Task, Task, int]] = []
        for day in sorted(by_day):
            ordered = sorted(by_day[day], key=lambda t: (t.start_minutes, t.end_minutes))
            for i, first in enumerate(ordered):
                for second in ordered[i + 1:]:
                    if second.start_minutes >= first.end_minutes:
                        break  # sorted by start, so nothing later can overlap `first`
                    overlap = min(first.end_minutes, second.end_minutes) - second.start_minutes
                    pairs.append((first, second, overlap))
        return pairs

    def detect_conflicts(self, date: Optional[str] = None, include_completed: bool = False) -> List[str]:
        """Return human-readable warnings for tasks whose time windows overlap (across all pets)."""
        warnings: List[str] = []
        for first, second, overlap in self.find_conflict_pairs(date, include_completed):
            scope = (
                "same pet" if first.pet_id == second.pet_id else "different pets, one owner"
            )
            warnings.append(
                f"Conflict on {first.date}: '{first.description}' ({self.pet_name_for(first)}, "
                f"{first.time}-{first.end_time}) overlaps '{second.description}' "
                f"({self.pet_name_for(second)}, {second.time}-{second.end_time}) "
                f"by {overlap} min [{scope}]."
            )
        return warnings

    # ---- feature 4: recurrence ------------------------------------------ #
    def handle_recurring_task(self, task: Task, pet: Optional[Pet] = None) -> Optional[Task]:
        """Spawn the next Daily/Weekly occurrence of a task via timedelta; return it (or None)."""
        delta = RECURRENCE_DELTAS.get(task.frequency)
        if delta is None:
            return None
        if pet is None:
            pet, _ = self.owner.find_task(task.id)
        if pet is None:
            raise ValueError("Cannot find the pet that owns this task.")

        next_date = (datetime.strptime(task.date, DATE_FMT) + delta).strftime(DATE_FMT)
        duplicate = any(
            t.description == task.description
            and t.time == task.time
            and t.date == next_date
            and not t.is_complete
            for t in pet.tasks
        )
        if duplicate:
            return None  # already scheduled; never double-spawn

        return pet.add_task(
            Task(
                description=task.description,
                time=task.time,
                date=next_date,
                category=task.category,
                priority=task.priority,
                duration_mins=task.duration_mins,
                frequency=task.frequency,
            )
        )

    def complete_task(self, task_id: str) -> Optional[Task]:
        """Mark a task complete and return the auto-generated next occurrence, if any."""
        pet, task = self.owner.find_task(task_id)
        if task is None:
            raise KeyError(f"No task with id {task_id!r}.")
        if task.is_complete:
            return None  # idempotent: completing twice must not spawn twice
        task.mark_complete()
        return self.handle_recurring_task(task, pet)

    # ---- feature 5: next available slot --------------------------------- #
    def get_free_windows(
        self,
        start_time: str = "08:00",
        end_time: str = "20:00",
        date: Optional[str] = None,
        pet: Optional[str] = None,
    ) -> List[Tuple[int, int]]:
        """Return free (start, end) minute windows inside the search range for a given day."""
        day = date or today_str()
        window_start, window_end = time_to_minutes(start_time), time_to_minutes(end_time)
        if window_start >= window_end:
            raise ValueError("start_time must be earlier than end_time.")

        if pet is not None:
            target = self.owner.get_pet(pet)
            if target is None:
                raise ValueError(f"Unknown pet {pet!r}.")
            pool = target.tasks
        else:
            pool = self.owner.get_all_tasks()

        busy = sorted(
            (t.start_minutes, t.end_minutes) for t in pool if t.date == day and not t.is_complete
        )
        free: List[Tuple[int, int]] = []
        cursor = window_start
        for busy_start, busy_end in busy:
            if busy_end <= cursor:
                continue
            if busy_start >= window_end:
                break
            if busy_start > cursor:
                free.append((cursor, busy_start))
            cursor = max(cursor, busy_end)
        if cursor < window_end:
            free.append((cursor, window_end))
        return free

    def find_next_available_slot(
        self,
        duration_mins: int,
        start_time: str = "08:00",
        end_time: str = "20:00",
        date: Optional[str] = None,
        pet: Optional[str] = None,
    ) -> Optional[str]:
        """Return the earliest 'HH:MM' start of a free window that fits duration_mins, else None."""
        if int(duration_mins) <= 0:
            raise ValueError("duration_mins must be a positive integer.")
        for free_start, free_end in self.get_free_windows(start_time, end_time, date, pet):
            if free_end - free_start >= duration_mins:
                return minutes_to_time(free_start)
        return None

    # ---- persistence passthrough ---------------------------------------- #
    def save_to_json(self, filepath: str) -> None:
        """Persist the scheduler's owner data to a JSON file."""
        JsonPersistence.save(self.owner, filepath)

    @classmethod
    def load_from_json(cls, filepath: str) -> "Scheduler":
        """Load owner data from a JSON file and return a scheduler bound to it."""
        return cls(JsonPersistence.load(filepath))
