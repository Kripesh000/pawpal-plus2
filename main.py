"""PawPal+ CLI demo: sorting, filtering, conflicts, recurrence, slot finding and JSON persistence."""

import os
import sys

from tabulate import tabulate

from pawpal_system import Owner, Pet, Scheduler, Task, minutes_to_time

DEMO_DATE = "2026-10-13"
DEMO_FILE = "data_demo.json"

# ANSI colours are used on a real terminal; piped output (e.g. into a README) stays plain.
USE_COLOR = (sys.stdout.isatty() or bool(os.environ.get("FORCE_COLOR"))) and not os.environ.get("NO_COLOR")
CODES = {"red": "31", "yellow": "33", "green": "32", "cyan": "36", "bold": "1", "dim": "2", "magenta": "35"}


def paint(text: str, *styles: str) -> str:
    """Wrap text in ANSI escape codes when colour output is enabled."""
    if not USE_COLOR or not styles:
        return text
    prefix = "".join(f"\033[{CODES[s]}m" for s in styles)
    return f"{prefix}{text}\033[0m"


PRIORITY_BADGE = {
    "High": lambda: paint("● High", "red", "bold"),
    "Medium": lambda: paint("● Medium", "yellow"),
    "Low": lambda: paint("● Low", "green"),
}


def status_badge(task: Task) -> str:
    """Return a coloured status badge for a task."""
    return paint("✔ Done", "green") if task.is_complete else paint("○ Pending", "cyan")


def heading(emoji: str, title: str) -> None:
    """Print a section heading."""
    print()
    print(paint(f"{emoji}  {title}", "bold", "magenta"))
    print(paint("─" * 74, "dim"))


def task_rows(scheduler: Scheduler, tasks):
    """Convert tasks into table rows."""
    return [
        [
            t.date,
            f"{t.time}-{t.end_time}",
            scheduler.pet_name_for(t),
            t.description,
            t.category,
            PRIORITY_BADGE[t.priority](),
            f"{t.duration_mins}m",
            t.frequency,
            status_badge(t),
        ]
        for t in tasks
    ]


HEADERS = ["Date", "Window", "Pet", "Task", "Category", "Priority", "Dur", "Repeat", "Status"]


def show(scheduler: Scheduler, tasks) -> None:
    """Print a formatted task table."""
    print(tabulate(task_rows(scheduler, tasks), headers=HEADERS, tablefmt="rounded_outline"))


def build_demo() -> Scheduler:
    """Create the demo owner, two pets and seven deliberately out-of-order tasks."""
    owner = Owner("Alex", "alex@example.com", id="owner-alex")
    luna = owner.add_pet(Pet("Luna", "Dog", "Labrador", 4, id="pet-luna"))
    mochi = owner.add_pet(Pet("Mochi", "Cat", "Siamese", 2, id="pet-mochi"))

    def add(pet, tid, desc, time, cat, prio, dur, freq="Once"):
        """Add one demo task to a pet."""
        pet.add_task(Task(desc, time, DEMO_DATE, cat, prio, dur, frequency=freq, id=tid))

    add(mochi, "t1", "Grooming brush-out", "18:00", "Grooming", "Low", 20, "Weekly")
    add(luna, "t2", "Evening training", "18:10", "Enrichment", "Medium", 30)
    add(luna, "t3", "Morning walk", "07:30", "Exercise", "High", 30, "Daily")
    add(mochi, "t4", "Breakfast", "07:45", "Feeding", "High", 15, "Daily")
    add(luna, "t5", "Heartworm pill", "12:00", "Medication", "High", 5)
    add(mochi, "t6", "Laser-pointer play", "09:00", "Enrichment", "Medium", 20)
    add(luna, "t7", "Dinner", "17:30", "Feeding", "High", 15, "Daily")
    return Scheduler(owner)


def main() -> None:
    """Run the full end-to-end demonstration."""
    scheduler = build_demo()
    owner = scheduler.owner

    print(paint("🐾  PawPal+ — Smart Pet Care Scheduler  (CLI demo)", "bold", "cyan"))
    print(f"Owner: {owner.name} <{owner.email}>   |   Demo date: {DEMO_DATE}")
    print("Pets : " + ", ".join(f"{p.name} the {p.species} ({p.breed}, {p.age}y)" for p in owner.pets))

    heading("📋", "1. Tasks as entered (unsorted)")
    show(scheduler, owner.get_all_tasks())

    heading("🔝", "2. Sorted by Priority (High → Low), then Date/Time")
    show(scheduler, scheduler.sort_tasks())

    heading("🕒", "2b. Sorted chronologically (day planner view)")
    show(scheduler, scheduler.sort_tasks(by="time"))

    heading("🔎", "3. Filtering")
    print(paint("Luna's tasks:", "bold"))
    show(scheduler, scheduler.sort_tasks(scheduler.filter_tasks(pet="Luna"), by="time"))
    print(paint("\nHigh-priority feeding tasks:", "bold"))
    show(scheduler, scheduler.filter_tasks(category="Feeding", priority="High"))

    heading("🚨", "4. Conflict detection (time + duration windows, across all pets)")
    conflicts = scheduler.detect_conflicts()
    for message in conflicts:
        print(paint("⚠️  " + message, "yellow"))
    print(paint(f"\n{len(conflicts)} conflict(s) found.", "bold"))

    heading("🔁", "5. Automated recurrence")
    for task_id in ("t3", "t1", "t5"):
        _, task = owner.find_task(task_id)
        spawned = scheduler.complete_task(task_id)
        done = paint(f"✔ Completed '{task.description}'", "green")
        if spawned:
            print(f"{done} ({task.frequency}) → new task auto-created for "
                  + paint(f"{spawned.date} {spawned.time}", "cyan", "bold"))
        else:
            print(f"{done} ({task.frequency}) → one-off, nothing to schedule.")
    print(paint("\nCalling complete_task('t3') again is a safe no-op: ", "dim")
          + f"spawned={scheduler.complete_task('t3')}")
    print()
    show(scheduler, scheduler.sort_tasks(scheduler.filter_tasks(status="Completed"), by="time"))
    print(paint("\nUpcoming (pending) after completions:", "bold"))
    show(scheduler, scheduler.sort_tasks(scheduler.filter_tasks(status="Pending"), by="time"))
    print(paint("\n✨ Walk was completed, so its 07:30 conflict with breakfast is now cleared:", "dim"))
    remaining = scheduler.detect_conflicts(date=DEMO_DATE)
    for message in remaining:
        print(paint("⚠️  " + message, "yellow"))
    if not remaining:
        print(paint("✅ No conflicts remain on " + DEMO_DATE + ".", "green"))

    heading("🧭", "6. Next available slot finder (search window 08:00-20:00)")
    rows = []
    for minutes in (20, 45, 90, 500):
        slot = scheduler.find_next_available_slot(minutes, "08:00", "20:00", DEMO_DATE)
        rows.append([f"{minutes} min", paint(slot, "green", "bold") if slot else paint("none free", "red")])
    print(tabulate(rows, headers=["Need", "Earliest start"], tablefmt="rounded_outline"))
    print(paint("\nFree windows on " + DEMO_DATE + ":", "bold"))
    windows = scheduler.get_free_windows("08:00", "20:00", DEMO_DATE)
    print(tabulate(
        [[minutes_to_time(a), minutes_to_time(b), f"{b - a} min"] for a, b in windows],
        headers=["From", "To", "Length"], tablefmt="rounded_outline"))

    heading("💾", "7. JSON persistence round-trip")
    scheduler.save_to_json(DEMO_FILE)
    print(f"Saved  → {DEMO_FILE} ({os.path.getsize(DEMO_FILE)} bytes)")
    reloaded = Scheduler.load_from_json(DEMO_FILE)
    same = reloaded.owner.to_dict() == scheduler.owner.to_dict()
    print(f"Loaded ← {DEMO_FILE}: {len(reloaded.owner.pets)} pets, {len(reloaded.owner.get_all_tasks())} tasks")
    print(paint("✅ Round-trip verified: reloaded data is identical to the original.", "green", "bold")
          if same else paint("❌ Round-trip mismatch!", "red", "bold"))
    os.remove(DEMO_FILE)
    print(paint(f"(Temporary {DEMO_FILE} removed.)", "dim"))
    print()


if __name__ == "__main__":
    main()
