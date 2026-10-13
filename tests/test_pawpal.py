"""Pytest suite for PawPal+ (tasks, pets, scheduling algorithms and persistence)."""

import json

import pytest

from pawpal_system import Owner, Pet, Scheduler, Task

DAY = "2026-10-13"


def make_task(desc="Walk", time="08:00", dur=30, prio="Medium", cat="Exercise",
              freq="Once", date=DAY, tid=None):
    """Build a task with sensible defaults for tests."""
    return Task(desc, time, date, cat, prio, dur, frequency=freq, id=tid)


@pytest.fixture
def world():
    """Return (owner, luna, mochi, scheduler) with a few pre-loaded tasks."""
    owner = Owner("Alex", "alex@example.com", id="o1")
    luna = owner.add_pet(Pet("Luna", "Dog", "Labrador", 4, id="p1"))
    mochi = owner.add_pet(Pet("Mochi", "Cat", "Siamese", 2, id="p2"))
    luna.add_task(make_task("Walk", "07:30", 30, "High", "Exercise", "Daily", tid="a"))
    luna.add_task(make_task("Pill", "12:00", 5, "High", "Medication", tid="b"))
    luna.add_task(make_task("Training", "18:10", 30, "Medium", "Enrichment", tid="c"))
    mochi.add_task(make_task("Breakfast", "07:45", 15, "High", "Feeding", "Daily", tid="d"))
    mochi.add_task(make_task("Grooming", "18:00", 20, "Low", "Grooming", "Weekly", tid="e"))
    return owner, luna, mochi, Scheduler(owner)


# ----------------------------- required tests ------------------------------ #
def test_task_completion_and_recurrence(world):
    """Completing tasks flips status and spawns the right next occurrence."""
    owner, luna, mochi, sched = world
    walk = luna.tasks[0]
    assert walk.status == "Pending"

    nxt = sched.complete_task("a")  # Daily
    assert walk.status == "Completed"
    assert nxt is not None and nxt.date == "2026-10-14" and nxt.time == "07:30"
    assert nxt.status == "Pending" and nxt.id != walk.id and nxt in luna.tasks

    nxt_weekly = sched.complete_task("e")  # Weekly
    assert nxt_weekly.date == "2026-10-20"

    assert sched.complete_task("b") is None  # Once -> no spawn
    assert sched.complete_task("a") is None  # already complete -> idempotent
    assert len([t for t in luna.tasks if t.description == "Walk"]) == 2


def test_pet_task_management():
    """Pets can add, list and remove tasks; task ownership is tracked."""
    pet = Pet("Luna", "Dog", id="p1")
    t1, t2 = make_task("A", tid="t1"), make_task("B", tid="t2")
    pet.add_task(t1)
    pet.add_task(t2)
    assert pet.get_tasks() == [t1, t2]
    assert t1.pet_id == "p1"

    t2.mark_complete()
    assert pet.get_tasks(status="Completed") == [t2]
    assert pet.get_tasks(status="pending") == [t1]

    assert pet.remove_task("t1") is True
    assert pet.remove_task("missing") is False
    assert pet.get_tasks() == [t2]
    with pytest.raises(ValueError):
        pet.add_task(make_task("dup", tid="t2"))

    owner = Owner("Alex")
    owner.add_pet(pet)
    assert owner.get_all_tasks() == [t2]
    assert owner.remove_pet(pet.id) is True and owner.get_all_tasks() == []


def test_scheduler_sorting_priority_and_time(world):
    """Sorting is High->Low, then date, then time, across all pets."""
    owner, luna, mochi, sched = world
    ordered = [t.description for t in sched.sort_tasks()]
    assert ordered == ["Walk", "Breakfast", "Pill", "Training", "Grooming"]

    chrono = [t.description for t in sched.sort_tasks(by="time")]
    assert chrono == ["Walk", "Breakfast", "Pill", "Grooming", "Training"]

    luna.add_task(make_task("Early low", "06:00", 10, "Low", tid="z"))
    luna.add_task(make_task("Tomorrow high", "06:00", 10, "High", date="2026-10-14", tid="y"))
    ordered = [t.description for t in sched.sort_tasks()]
    assert ordered[:3] == ["Walk", "Breakfast", "Pill"]       # High, same-day by time
    assert ordered[3] == "Tomorrow high"                       # High, later date
    with pytest.raises(ValueError):
        sched.sort_tasks(by="mood")


def test_scheduler_filtering(world):
    """Filters work individually, combined, and by pet id or name."""
    owner, luna, mochi, sched = world
    assert {t.description for t in sched.filter_tasks(pet="Luna")} == {"Walk", "Pill", "Training"}
    assert {t.description for t in sched.filter_tasks(pet="p2")} == {"Breakfast", "Grooming"}
    assert [t.description for t in sched.filter_tasks(category="feeding")] == ["Breakfast"]
    assert {t.description for t in sched.filter_tasks(priority="High")} == {"Walk", "Pill", "Breakfast"}
    assert [t.description for t in sched.filter_tasks(pet="Luna", priority="High", category="Medication")] == ["Pill"]

    sched.complete_task("b")
    assert [t.description for t in sched.filter_tasks(status="Completed")] == ["Pill"]
    assert len(sched.filter_tasks(status="Pending")) == 4  # 5 tasks; only the one-off 'Pill' is done
    assert sched.filter_tasks(pet="Nobody") == []
    assert sched.filter_tasks(date="1999-01-01") == []


def test_conflict_detection_overlap(world):
    """Overlapping windows (even across pets) warn; back-to-back and completed tasks do not."""
    owner, luna, mochi, sched = world
    warnings = sched.detect_conflicts()
    assert len(warnings) == 2
    assert "Walk" in warnings[0] and "Breakfast" in warnings[0] and "15 min" in warnings[0]
    assert "Grooming" in warnings[1] and "Training" in warnings[1] and "10 min" in warnings[1]
    assert "different pets" in warnings[0]

    # Back-to-back (08:00 ends exactly when 08:00 starts) is NOT a conflict.
    luna.add_task(make_task("Edge A", "09:00", 30, tid="x1"))
    mochi.add_task(make_task("Edge B", "09:30", 30, tid="x2"))
    assert len(sched.detect_conflicts()) == 2

    # Full containment and same-pet overlap are caught.
    luna.add_task(make_task("Inside", "09:10", 5, tid="x3"))
    assert len(sched.detect_conflicts()) == 3
    assert any("same pet" in w and "Inside" in w for w in sched.detect_conflicts())

    # Completing a task removes its conflicts unless include_completed is set.
    sched.complete_task("a")
    assert len(sched.detect_conflicts()) == 2
    assert len(sched.detect_conflicts(include_completed=True)) == 3
    assert sched.detect_conflicts(date="2030-01-01") == []


def test_next_available_slot_finder(world):
    """The finder returns the earliest gap that fits, honours the window and reports None."""
    owner, luna, mochi, sched = world
    # Busy: 07:30-08:00(+07:45-08:00), 12:00-12:05, 18:00-18:20, 18:10-18:40
    assert sched.find_next_available_slot(30, "07:00", "20:00", DAY) == "07:00"  # exact fit: 07:00-07:30
    assert sched.find_next_available_slot(45, "07:00", "20:00", DAY) == "08:00"  # 07:00-07:30 too short
    assert sched.find_next_available_slot(30, "06:00", "20:00", DAY) == "06:00"
    assert sched.find_next_available_slot(240, "08:00", "20:00", DAY) == "08:00"
    assert sched.find_next_available_slot(241, "08:00", "20:00", DAY) == "12:05"  # 08:00-12:00 too short
    assert sched.find_next_available_slot(355, "08:00", "20:00", DAY) == "12:05"  # exact: 12:05-18:00
    assert sched.find_next_available_slot(356, "08:00", "20:00", DAY) is None
    assert sched.find_next_available_slot(60, "17:30", "20:00", DAY) == "18:40"
    assert sched.find_next_available_slot(30, date="2030-01-01") == "08:00"       # empty day

    # Per-pet view ignores the other pet's tasks.
    assert sched.find_next_available_slot(45, "07:00", "20:00", DAY, pet="Mochi") == "07:00"
    assert sched.find_next_available_slot(60, "07:00", "20:00", DAY, pet="Mochi") == "08:00"
    assert sched.find_next_available_slot(20, "07:00", "20:00", DAY, pet="Luna") == "07:00"

    # Result never overlaps anything it was asked to avoid.
    slot = sched.find_next_available_slot(45, "07:00", "20:00", DAY)
    probe = make_task("Probe", slot, 45, tid="probe")
    luna.add_task(probe)
    assert all("Probe" not in w for w in sched.detect_conflicts())

    # Completed tasks free up their time.
    sched.complete_task("a")
    sched.complete_task("d")
    assert sched.find_next_available_slot(60, "07:00", "09:00", DAY) == "07:00"

    with pytest.raises(ValueError):
        sched.find_next_available_slot(0)
    with pytest.raises(ValueError):
        sched.find_next_available_slot(10, "20:00", "08:00", DAY)


def test_json_persistence_roundtrip(world, tmp_path):
    """Saving then loading reproduces the identical object graph; bad files fail clearly."""
    owner, luna, mochi, sched = world
    sched.complete_task("a")  # include a Completed task and a spawned recurrence
    path = tmp_path / "data.json"

    owner.save_to_json(str(path))
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["version"] == 1 and on_disk["owner"]["name"] == "Alex"

    loaded = Owner.load_from_json(str(path))
    assert loaded.to_dict() == owner.to_dict()
    assert len(loaded.pets) == 2 and len(loaded.get_all_tasks()) == 6
    assert loaded.get_pet("luna").tasks[0].is_complete
    assert all(t.pet_id == p.id for p in loaded.pets for t in p.tasks)

    reloaded_sched = Scheduler.load_from_json(str(path))
    assert reloaded_sched.detect_conflicts() == Scheduler(loaded).detect_conflicts()
    reloaded_sched.save_to_json(str(tmp_path / "again.json"))
    assert Owner.load_from_json(str(tmp_path / "again.json")).to_dict() == owner.to_dict()

    with pytest.raises(FileNotFoundError):
        Owner.load_from_json(str(tmp_path / "nope.json"))
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        Owner.load_from_json(str(bad))
    incomplete = tmp_path / "incomplete.json"
    incomplete.write_text(json.dumps({"owner": {"pets": []}}), encoding="utf-8")
    with pytest.raises(ValueError):
        Owner.load_from_json(str(incomplete))


# ------------------------------ extra edge cases --------------------------- #
def test_recurrence_crosses_month_and_year_boundaries():
    """timedelta arithmetic handles month-end, year-end and leap days correctly."""
    owner = Owner("A")
    pet = owner.add_pet(Pet("P", "Dog"))
    sched = Scheduler(owner)
    cases = [("2026-10-31", "Daily", "2026-11-01"), ("2026-12-31", "Daily", "2027-01-01"),
             ("2028-02-28", "Daily", "2028-02-29"), ("2026-12-29", "Weekly", "2027-01-05")]
    for i, (start, freq, expected) in enumerate(cases):
        task = pet.add_task(make_task(f"T{i}", date=start, freq=freq, tid=f"r{i}"))
        assert sched.complete_task(task.id).date == expected


def test_recurrence_does_not_create_duplicates():
    """If the next occurrence already exists, no second copy is spawned."""
    owner = Owner("A")
    pet = owner.add_pet(Pet("P", "Dog"))
    sched = Scheduler(owner)
    task = pet.add_task(make_task("Walk", freq="Daily", tid="w"))
    pet.add_task(make_task("Walk", date="2026-10-14", freq="Daily", tid="w2"))
    assert sched.complete_task("w") is None
    assert len(pet.tasks) == 2
    with pytest.raises(KeyError):
        sched.complete_task("ghost")


def test_task_validation():
    """Invalid input is rejected with a ValueError instead of corrupting the schedule."""
    for kwargs in (
        dict(time="25:00"), dict(time="8am"), dict(date="13/10/2026"), dict(prio="Urgent"),
        dict(dur=0), dict(dur=-5), dict(freq="Hourly"), dict(desc="   "),
    ):
        with pytest.raises(ValueError):
            make_task(**kwargs)
    with pytest.raises(ValueError):
        Pet("", "Dog")
    with pytest.raises(ValueError):
        Owner(" ")


def test_task_running_past_midnight_is_clamped():
    """A task that would run past 24:00 is clamped to the end of the day for overlap math."""
    task = make_task("Late", "23:50", 30)
    assert task.end_minutes == 1440 and task.end_time == "24:00"
