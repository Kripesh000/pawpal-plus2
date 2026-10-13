# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

PawPal+ is built around four domain classes and one helper:

- **`Task`** – a single care activity (description, `HH:MM` time, `YYYY-MM-DD` date, category, priority, duration, status, frequency). It validates its own input so bad data can't enter the system, and exposes `start_minutes` / `end_minutes` so algorithms never re-parse strings.
- **`Pet`** – owns a list of tasks and stamps each with its `pet_id`.
- **`Owner`** – owns a list of pets and flattens them with `get_all_tasks()`.
- **`Scheduler`** – holds a reference to an `Owner` and contains every algorithm (sort, filter, conflicts, recurrence, free-slot search).
- **`JsonPersistence`** – saves/loads the whole object graph; `Owner` and `Scheduler` delegate to it.

*Core user actions, in plain language:*
1. "I want to add my dog and my cat."
2. "I want to add a walk for Luna at 7:30 for 30 minutes, and have it repeat every day."
3. "Show me today's plan, most important things first."
4. "Warn me if two things overlap, even if they're for different pets, because I can only be in one place."
5. "When I tick off the walk, schedule tomorrow's automatically."
6. "I need 45 minutes for a vet-prep brush-out. When am I actually free?"
7. "Remember all of this next time I open the app."

**b. Design changes**

- **Recurrence lives in `Scheduler`, not `Task.mark_complete()`.** The obvious design is for a task to spawn its successor when completed, but a `Task` only knows its `pet_id`, not the `Pet` object it must be added to. Having `mark_complete()` stay a simple state change, and letting `Scheduler.complete_task()` orchestrate "mark done + spawn next", keeps `Task` free of upward references and made both halves independently testable.
- **Tasks carry a `pet_id`.** Cross-pet algorithms (sorting, conflicts) return flat task lists, so each task needs to know who it belongs to for readable warnings. `Pet.add_task()` sets it automatically, which keeps it from going out of sync.
- **`JsonPersistence` became its own class** instead of loose functions, so the schema version and atomic-write logic have one home.
- **Idempotent completion.** Early on, completing a task twice would have spawned two successors. `complete_task()` now returns `None` for an already-completed task, and spawn de-duplicates against existing future tasks.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

The scheduler considers **priority**, **date/time**, **duration**, **status** (completed tasks stop blocking time), **pet**, **category**, and **frequency**. Priority outranks time when sorting because a missed medication matters more than a perfectly tidy timeline. Time and duration drive conflict and slot logic because they are the only hard constraints: an owner cannot do two things at once.

**b. Tradeoffs**

- **Exact-start matching vs. duration-window overlap.** The simplest conflict check flags only tasks that start at the *same* minute. It's easy to write and explain, but it misses a 07:30 walk running over a 07:45 breakfast. I chose full interval overlap (`start < other_end and other_start < end`) over exact-time matching: slightly more logic, far fewer missed conflicts. Windows are half-open, so back-to-back tasks are *not* conflicts.
- **Warn, don't auto-fix.** The scheduler reports conflicts and can suggest a free slot, but never moves tasks itself. Auto-rescheduling would need to guess owner preferences (is the walk or the breakfast movable?), and silently changing a medication time is worse than a visible warning.
- **Owner as a single resource.** Overlaps are flagged across different pets because one person performs all tasks. If a household had several caretakers this would over-warn; a future `assigned_to` field would fix it.
- **Simplicity of the sweep.** Conflict detection sorts by start and exits early, which is fast, and reports each overlapping *pair*. A 3-way overlap therefore shows up as up to 3 warnings rather than one cluster. I accepted slightly noisier output for much simpler code.
- **Single-day tasks.** A task that would run past midnight is clamped to 24:00 rather than modelled across two dates.

---

## 3. AI Collaboration

**a. How you used AI**

AI was used for scaffolding the class structure from a written specification, drafting the algorithms, generating the test suite, and writing documentation. The most effective prompts were **specification-style**: exact class names, attribute lists, method signatures and file names, plus explicit success criteria ("all tests pass", "valid Mermaid"). Vague prompts ("make a scheduler") produce plausible but generic code. See `ai_interactions.md` for the workflow log.

**b. Judgment and verification**

I did not accept the first draft of the tests as-is. Before running them I hand-traced each expected value against the algorithm and found several of my own expectations were wrong, not the code: for example, a free window of exactly 30 minutes *does* fit a 30-minute task (I had asserted it didn't), and a 12:05–18:00 gap fits a 250-minute task (I had asserted "no slot"). The code was right and the tests were wrong. Passing tests prove little if the tests encode a mistake, so I also **mutation-tested** the suite: I deliberately broke the code in seven ways (weekly = +1 day, sort ignoring priority, off-by-one in overlap and in slot fitting, completed tasks still blocking time, double-spawn on re-completion, status dropped on save) and confirmed a test failed for each. During that process one result looked wrong (a weekly-recurrence bug apparently failed the *conflict* tests instead of the recurrence test). Rather than shrug it off I investigated and found the cause was stale Python bytecode in my test harness, not a gap in the tests, then re-ran everything with caching disabled.

---

## 4. Testing and Verification

**a. What you tested**

- Completion and recurrence (daily, weekly, one-off, double-completion, month/year/leap-day boundaries, no duplicates).
- Pet task add/remove/filter and ownership.
- Sorting: priority tier, then date/time, across pets; the alternate chronological mode.
- Filtering: each criterion alone, combined, by pet name or id, empty results.
- Conflicts: partial overlap, containment, same-pet vs. cross-pet, back-to-back (not a conflict), completed tasks ignored.
- Slot finder: exact fit, too-small gaps, window edges, per-pet vs. household, empty day, invalid arguments.
- Persistence: full round-trip equality, completed status preserved, missing / corrupt / incomplete files.
- Input validation: bad times, dates, priorities, durations, empty names.

These matter because the scheduler's value is *trustworthy* output: a wrong conflict or a missing medication reminder is worse than no tool at all.

**b. Confidence**

High for the scheduling and persistence core: it is covered by assertions on exact values plus mutation testing. Moderate for the Streamlit UI, which is thin glue over the tested core and has no automated tests. Next I would test: tasks spanning midnight, time zones / DST, very large task counts, concurrent edits to `data.json` from two browser tabs, and a property-based test asserting that `find_next_available_slot` never returns a slot that `detect_conflicts` would flag.

---

## 5. Reflection

**a. What went well**

Keeping all algorithms in one `Scheduler` that operates on plain task lists made everything composable (filter → sort → display) and easy to test, with the CLI, the web UI and the tests all driving the exact same code.

**b. What you would improve**

Add an `assigned_to` caretaker field so conflicts only fire for the same person; let the scheduler propose automatic resolutions for the user to approve; support multi-day and time-zone-aware tasks; and add real UI tests (e.g. Streamlit's `AppTest`).

**c. Key takeaway**

Tests written by the same author (human or AI) as the code can share its blind spots. The most valuable verification step was independent: hand-computing expected values and then deliberately breaking the code to prove the tests could fail.
