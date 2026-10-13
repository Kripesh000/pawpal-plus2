"""PawPal+ Streamlit UI: owner/pet management, task management, schedule views, slot finder, persistence."""

import json
import os
from datetime import date, time

import streamlit as st
from tabulate import tabulate

from pawpal_system import (
    PRIORITIES,
    FREQUENCIES,
    Owner,
    Pet,
    Scheduler,
    Task,
    minutes_to_time,
    time_to_minutes,
)

DATA_FILE = "data.json"
PRIORITY_BADGE = {"High": "🔴 High", "Medium": "🟡 Medium", "Low": "🟢 Low"}
CATEGORIES = ["Exercise", "Feeding", "Medication", "Grooming", "Enrichment", "Vet", "General"]
CATEGORY_EMOJI = {
    "Exercise": "🦮", "Feeding": "🍽️", "Medication": "💊", "Grooming": "🛁",
    "Enrichment": "🧶", "Vet": "🩺", "General": "📌",
}
SPECIES_EMOJI = {"Dog": "🐶", "Cat": "🐱", "Bird": "🦜", "Rabbit": "🐰", "Other": "🐾"}

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="wide")


# --------------------------------------------------------------------------- #
# State helpers
# --------------------------------------------------------------------------- #
def init_state() -> None:
    """Create the session-persistent Owner, loading data.json automatically when it exists."""
    if "owner" in st.session_state:
        return
    st.session_state.owner = Owner("Jordan")
    st.session_state.flash = []
    if os.path.exists(DATA_FILE):
        try:
            st.session_state.owner = Owner.load_from_json(DATA_FILE)
            st.session_state.flash.append(("success", f"Loaded saved data from {DATA_FILE}."))
        except (ValueError, OSError) as exc:
            st.session_state.flash.append(("error", f"Could not load {DATA_FILE}: {exc}"))


def flash(kind: str, message: str) -> None:
    """Queue a message to display after the next rerun."""
    st.session_state.setdefault("flash", []).append((kind, message))


def show_flash() -> None:
    """Display and clear any queued messages."""
    for kind, message in st.session_state.pop("flash", []):
        getattr(st, kind)(message)


def load_sample_data() -> None:
    """Replace the current data with a small sample household dated today."""
    today = date.today().isoformat()
    owner = Owner(st.session_state.owner.name or "Jordan", st.session_state.owner.email)
    luna = owner.add_pet(Pet("Luna", "Dog", "Labrador", 4))
    mochi = owner.add_pet(Pet("Mochi", "Cat", "Siamese", 2))
    luna.add_task(Task("Morning walk", "07:30", today, "Exercise", "High", 30, frequency="Daily"))
    luna.add_task(Task("Dinner", "17:30", today, "Feeding", "High", 15, frequency="Daily"))
    luna.add_task(Task("Evening training", "18:10", today, "Enrichment", "Medium", 30))
    mochi.add_task(Task("Breakfast", "07:45", today, "Feeding", "High", 15, frequency="Daily"))
    mochi.add_task(Task("Grooming", "18:00", today, "Grooming", "Low", 20, frequency="Weekly"))
    st.session_state.owner = owner


def task_rows(scheduler: Scheduler, tasks) -> list:
    """Convert tasks into display rows (list of dicts) with emoji and status badges."""
    return [
        {
            "Date": t.date,
            "Time": f"{t.time}–{t.end_time}",
            "Pet": scheduler.pet_name_for(t),
            "Task": f"{CATEGORY_EMOJI.get(t.category, '📌')} {t.description}",
            "Category": t.category,
            "Priority": PRIORITY_BADGE[t.priority],
            "Duration": f"{t.duration_mins} min",
            "Repeat": t.frequency,
            "Status": "✅ Done" if t.is_complete else "⏳ Pending",
        }
        for t in tasks
    ]


# --------------------------------------------------------------------------- #
# Page
# --------------------------------------------------------------------------- #
init_state()
st.session_state.setdefault("sched_day", date.today())
st.session_state.setdefault("sched_all", False)
owner: Owner = st.session_state.owner
scheduler = Scheduler(owner)

st.title("🐾 PawPal+")
st.caption("Smart pet care scheduling: priorities, conflict warnings, recurring tasks and free-slot finding.")
show_flash()

# ---- Sidebar: owner profile + persistence -------------------------------- #
with st.sidebar:
    st.header("👤 Owner")
    new_name = st.text_input("Name", value=owner.name)
    if new_name.strip():
        owner.name = new_name.strip()
    owner.email = st.text_input("Email", value=owner.email)

    st.header("💾 Data")
    col_save, col_load = st.columns(2)
    if col_save.button("Save", help=f"Write everything to {DATA_FILE}"):
        try:
            owner.save_to_json(DATA_FILE)
            flash("success", f"Saved to {DATA_FILE}.")
        except OSError as exc:
            flash("error", f"Save failed: {exc}")
        st.rerun()
    if col_load.button("Load", help=f"Read everything from {DATA_FILE}"):
        try:
            st.session_state.owner = Owner.load_from_json(DATA_FILE)
            flash("success", f"Loaded from {DATA_FILE}.")
        except FileNotFoundError:
            flash("warning", f"{DATA_FILE} does not exist yet; save first.")
        except (ValueError, OSError) as exc:
            flash("error", f"Load failed: {exc}")
        st.rerun()

    st.download_button(
        "⬇️ Download JSON",
        data=json.dumps({"version": 1, "owner": owner.to_dict()}, indent=2),
        file_name="pawpal_data.json",
        mime="application/json",
    )
    if st.button("🧪 Load sample data", help="Replaces current data with a demo household"):
        load_sample_data()
        flash("info", "Sample data loaded (not saved until you press Save).")
        st.rerun()

# ---- Summary metrics ------------------------------------------------------ #
all_tasks = owner.get_all_tasks()
pending = [t for t in all_tasks if not t.is_complete]
conflict_count = len(scheduler.detect_conflicts())
m1, m2, m3, m4 = st.columns(4)
m1.metric("🐾 Pets", len(owner.pets))
m2.metric("⏳ Pending", len(pending))
m3.metric("✅ Completed", len(all_tasks) - len(pending))
m4.metric("⚠️ Conflicts", conflict_count)

tab_pets, tab_tasks, tab_schedule, tab_slots = st.tabs(
    ["🐶 Pets", "➕ Tasks", "📅 Schedule", "🧭 Slot Finder"]
)

# ---- Pets tab ------------------------------------------------------------- #
with tab_pets:
    st.subheader("Add a pet")
    with st.form("add_pet_form"):
        c1, c2, c3, c4 = st.columns(4)
        pet_name = c1.text_input("Name")
        species = c2.selectbox("Species", list(SPECIES_EMOJI))
        breed = c3.text_input("Breed", value="Unknown")
        age = c4.number_input("Age (years)", min_value=0, max_value=40, value=1)
        if st.form_submit_button("Add pet"):
            try:
                owner.add_pet(Pet(pet_name, species, breed, int(age)))
                flash("success", f"Added {pet_name.strip()} {SPECIES_EMOJI[species]}")
            except ValueError as exc:
                flash("error", str(exc))
            st.rerun()

    st.subheader("Your pets")
    if not owner.pets:
        st.info("No pets yet. Add one above, or load the sample data from the sidebar.")
    for pet in owner.pets:
        c1, c2, c3 = st.columns([4, 2, 1])
        c1.markdown(
            f"### {SPECIES_EMOJI.get(pet.species, '🐾')} {pet.name}  \n"
            f"{pet.species} · {pet.breed} · {pet.age} yr"
        )
        c2.metric("Tasks", len(pet.tasks))
        if c3.button("🗑️ Remove", key=f"rm_pet_{pet.id}"):
            owner.remove_pet(pet.id)
            flash("info", f"Removed {pet.name} and their tasks.")
            st.rerun()

# ---- Tasks tab ------------------------------------------------------------ #
with tab_tasks:
    st.subheader("Add a task")
    if not owner.pets:
        st.info("Add a pet first.")
    else:
        with st.form("add_task_form"):
            c1, c2 = st.columns(2)
            pet_choice = c1.selectbox("Pet", owner.pets, format_func=lambda p: f"{p.name} ({p.species})")
            description = c2.text_input("Description", value="Morning walk")
            c3, c4, c5, c6 = st.columns(4)
            category = c3.selectbox("Category", CATEGORIES)
            priority = c4.selectbox("Priority", PRIORITIES, index=1)
            duration = c5.number_input("Duration (min)", min_value=1, max_value=600, value=20)
            frequency = c6.selectbox("Repeats", FREQUENCIES)
            c7, c8 = st.columns(2)
            task_date = c7.date_input("Date", value=date.today())
            task_time = c8.time_input("Start time", value=time(8, 0))
            submitted = st.form_submit_button("Add task")
        if submitted:
            try:
                task = pet_choice.add_task(
                    Task(description, task_time.strftime("%H:%M"), task_date.isoformat(),
                         category, priority, int(duration), frequency=frequency)
                )
                flash("success", f"Added '{task.description}' for {pet_choice.name} on "
                 f"{task.date} at {task.time}-{task.end_time}. "
                 "(Use the Schedule tab's 'Day' picker or 'All dates' to view it.)")
                for first, second, overlap in scheduler.find_conflict_pairs(date=task.date):
                    if task.id in (first.id, second.id):
                        other = second if first.id == task.id else first
                        flash("warning", f"⚠️ '{task.description}' ({task.time}-{task.end_time}) overlaps "
                                         f"'{other.description}' ({scheduler.pet_name_for(other)}, "
                                                                                  f"{other.time}-{other.end_time}) by {overlap} min.")
                st.session_state["sched_day"] = task_date   # Schedule tab jumps to this day
                st.session_state["sched_all"] = False
            except ValueError as exc:
                flash("error", str(exc))
            st.rerun()

    st.subheader("Manage tasks")
    if not all_tasks:
        st.info("No tasks yet.")
    else:
        header = st.columns([1.3, 1.6, 1.2, 3, 1.2, 1.2, 1.2])
        for col, label in zip(header, ["Date", "Time", "Pet", "Task", "Priority", "", ""]):
            col.markdown(f"**{label}**")
        for task in scheduler.sort_tasks(by="time"):
            c = st.columns([1.3, 1.6, 1.2, 3, 1.2, 1.2, 1.2])
            c[0].write(task.date)
            c[1].write(f"{task.time}–{task.end_time}")
            c[2].write(scheduler.pet_name_for(task))
            label = f"{CATEGORY_EMOJI.get(task.category, '📌')} {task.description}"
            c[3].write(f"~~{label}~~" if task.is_complete else label)
            c[4].write(PRIORITY_BADGE[task.priority])
            if not task.is_complete and c[5].button("✅ Done", key=f"done_{task.id}"):
                spawned = scheduler.complete_task(task.id)
                if spawned:
                    flash("success", f"Completed '{task.description}'. Next {task.frequency.lower()} "
                                     f"occurrence scheduled for {spawned.date} at {spawned.time}.")
                elif task.frequency != "Once":
                    flash("info", f"Completed '{task.description}'. No new {task.frequency.lower()} task was "
                                  "created because the next occurrence is already scheduled.")
                else:
                    flash("success", f"Completed '{task.description}'.")
                st.rerun()
            if c[6].button("🗑️", key=f"del_{task.id}", help="Delete task"):
                pet, _ = owner.find_task(task.id)
                pet.remove_task(task.id)
                flash("info", f"Deleted '{task.description}'.")
                st.rerun()

# ---- Schedule tab --------------------------------------------------------- #
with tab_schedule:
    st.subheader("Schedule")
    f1, f2, f3, f4, f5 = st.columns(5)
    show_all_dates = f1.checkbox("All dates", key="sched_all")
    chosen_date = f1.date_input("Day", key="sched_day", disabled=show_all_dates)
    pet_filter = f2.selectbox("Pet", ["All"] + [p.name for p in owner.pets])
    status_filter = f3.selectbox("Status", ["All", "Pending", "Completed"])
    category_filter = f4.selectbox("Category", ["All"] + CATEGORIES)
    priority_filter = f5.selectbox("Priority", ["All"] + list(PRIORITIES))
    sort_mode = st.radio(
        "Sort by", ["Priority, then time", "Time only"], horizontal=True,
    )

    day_key = None if show_all_dates else chosen_date.isoformat()
    with st.expander("🔍 Debug: what is stored vs. what this view shows"):
        st.write(f"Viewing day: **{day_key or 'ALL dates'}**  |  tasks stored: **{len(all_tasks)}**")
        if all_tasks:
            st.table([{"Date": t.date, "Time": t.time, "Pet": scheduler.pet_name_for(t),
                       "Task": t.description, "Status": t.status} for t in all_tasks])
    visible = scheduler.filter_tasks(
        status=None if status_filter == "All" else status_filter,
        pet=None if pet_filter == "All" else pet_filter,
        category=None if category_filter == "All" else category_filter,
        priority=None if priority_filter == "All" else priority_filter,
        date=day_key,
    )
    visible = scheduler.sort_tasks(visible, by="priority" if sort_mode.startswith("Priority") else "time")

    warnings = scheduler.detect_conflicts(date=day_key)
    if warnings:
        st.error(f"🚨 {len(warnings)} scheduling conflict(s) need attention:")
        for message in warnings:
            st.warning("⚠️ " + message)
    elif all_tasks:
        st.success("✅ No scheduling conflicts for this view.")

    hidden = len(all_tasks) - len(visible)
    if hidden > 0:
        st.caption(f"ℹ️ Showing {len(visible)} of {len(all_tasks)} tasks. {hidden} hidden by the "
               "day/filters above (tick 'All dates' and set filters to 'All' to see everything).")
    if not visible:
        st.info("No tasks match these filters.")
    else:
        rows = task_rows(scheduler, visible)
        st.dataframe(rows, hide_index=True)
        with st.expander("📄 Plain-text report (tabulate)"):
            st.code(tabulate(rows, headers="keys", tablefmt="rounded_outline"), language=None)

# ---- Slot finder tab ------------------------------------------------------ #
with tab_slots:
    st.subheader("Next available slot")
    st.caption("Finds the earliest gap that fits a new task without overlapping pending tasks.")
    s1, s2, s3, s4, s5 = st.columns(5)
    slot_date = s1.date_input("Date", value=date.today(), key="slot_date")
    slot_duration = s2.number_input("Needed (min)", min_value=1, max_value=600, value=30)
    window_start = s3.time_input("Earliest", value=time(8, 0), key="slot_from")
    window_end = s4.time_input("Latest", value=time(20, 0), key="slot_to")
    slot_pet = s5.selectbox("Whose schedule?", ["Whole household"] + [p.name for p in owner.pets])

    start_str, end_str = window_start.strftime("%H:%M"), window_end.strftime("%H:%M")
    if time_to_minutes(start_str) >= time_to_minutes(end_str):
        st.error("'Earliest' must be before 'Latest'.")
    else:
        pet_arg = None if slot_pet == "Whole household" else slot_pet
        slot = scheduler.find_next_available_slot(
            int(slot_duration), start_str, end_str, slot_date.isoformat(), pet_arg
        )
        if slot:
            finish = minutes_to_time(time_to_minutes(slot) + int(slot_duration))
            st.success(f"🎯 Next available {int(slot_duration)}-minute slot: **{slot} – {finish}**")
        else:
            st.error(f"No {int(slot_duration)}-minute gap between {start_str} and {end_str}.")
        windows = scheduler.get_free_windows(start_str, end_str, slot_date.isoformat(), pet_arg)
        if windows:
            st.markdown("**All free windows**")
            st.table(
                [{"From": minutes_to_time(a), "To": minutes_to_time(b), "Length": f"{b - a} min",
                  "Fits?": "✅" if b - a >= slot_duration else "—"} for a, b in windows]
            )
