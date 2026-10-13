# AI Interactions Log

## Part 1 — Agent Workflow

### Task given to the agent
A single, specification-style prompt asked the agent to act as a lead architect and build **PawPal+** end to end — core classes (`Task`, `Pet`, `Owner`, `Scheduler`), five algorithmic features (sorting, filtering, conflict detection, automated recurrence, next-available-slot finder), JSON persistence, a Streamlit UI, a `tabulate`/ANSI CLI demo, a pytest suite, a Mermaid UML diagram, and documentation — targeting all core requirements plus the five stretch challenges. It also specified exact file names, class/method names, test names, and a one-line docstring on every method.

### Files created or modified
| File | Action |
|---|---|
| `pawpal_system.py` | Created — domain model, `Scheduler`, `JsonPersistence` |
| `main.py` | Created — CLI demo |
| `tests/test_pawpal.py`, `conftest.py` | Created — 11 tests; root `conftest.py` makes imports work for plain `pytest` too |
| `app.py` | Replaced the starter placeholder with the full Streamlit UI |
| `diagrams/uml_final.mmd` | Created |
| `README.md`, `reflection.md`, `ai_interactions.md` | Rewritten from the starter templates |
| `requirements.txt`, `.gitignore` | Updated (`tabulate`, `wcwidth`; ignore `data.json`) |

### Agent execution steps
1. Inspected the uploaded starter repo (listed the zip, then read `app.py`, README, reflection template, requirements).
2. Checked the environment: `tabulate` was present; `pytest` and `streamlit` were **not installed and there was no network access**.
3. Implemented `pawpal_system.py` with validation, a sweep-line conflict detector, `timedelta`-based recurrence, and a gap-walking slot finder.
4. Built and ran `main.py`; reviewed the output by hand (e.g. confirmed the 07:30–08:00 walk overlaps the 07:45–08:00 breakfast by 15 min).
5. Wrote the test suite; because pytest was unavailable, ran it through a throwaway stand-in runner (`fixture`, `raises`, `tmp_path` only; not part of the repo).
6. **Mutation-tested** the suite with seven deliberately injected bugs.
7. Built `app.py`, then smoke-tested every UI path against a fake `streamlit` stub (since the real package wasn't installable).
8. Wrote the UML, README (embedding the *actual* captured CLI output), and reflection.

### Manual corrections made along the way
- **Test expectations were wrong, not the code.** Hand-tracing found five bad assertions (exact-fit gaps *do* fit; a 12:05–18:00 gap fits 250 min; Mochi has a 45-min gap at 07:00; a pending count was off by one; one conflict assertion indexed the wrong pair). Fixed before trusting any green result.
- **A tautological assertion** (`... == 3 + 0 or True`) slipped into a first draft of the conflict test and was replaced with a real assertion.
- **Misleading mutation result.** One injected bug appeared to fail the wrong tests. Root cause: Python reused stale `.pyc` bytecode because two mutated files were the same size and modified in the same second. Re-ran with `PYTHONDONTWRITEBYTECODE=1`; all seven bugs were then caught by the expected tests.
- **Emoji alignment.** `tabulate` mis-measures double-width emoji without `wcwidth`, breaking table borders, so emoji were moved out of CLI table cells (they remain in headings, messages and the Streamlit UI) and `wcwidth` was added to `requirements.txt`.
- **API tidy-ups:** `_pet_name` made public as `pet_name_for` because the CLI and UI both need it; a mid-function `import` in `app.py` moved to the top.

### What was *not* verified (be aware)
- The sandbox had no pytest, so **real `python -m pytest` output was not captured**; the README has a marked block to paste yours into.
- The Streamlit app was exercised only against a stub, **not the real `streamlit run`**, so run it once and click through the tabs.
- The Mermaid file was syntax-checked structurally but not rendered with Mermaid.

---

## Part 2 — Model / Prompt Comparison: Recurring-Task Datetime Math

> **Status: template to complete.** I have not run Claude 3.5 Sonnet or GPT-4o on this task, so no outputs are reported below. Fill in the "Observed" fields from real runs; the prompt, test cases, and rubric are ready to use.

### The prompt (identical for both models)
```text
In Python, write `handle_recurring_task(task, pet)` for a pet-care app. `task` has
`date` ("YYYY-MM-DD"), `time` ("HH:MM"), `frequency` ("Once" | "Daily" | "Weekly"),
`description`, `priority`, `duration_mins`, `category`, `status`. When a Daily or
Weekly task is completed, create and attach to the pet the next occurrence
(same fields, status "Pending", new id, date advanced). Use datetime.timedelta.
Return the new Task or None. Do not create duplicates.
```

### Shared test cases (ground truth from this repo's implementation)
| Input date | Frequency | Expected next date |
|---|---|---|
| 2026-10-13 | Daily | 2026-10-14 |
| 2026-10-13 | Weekly | 2026-10-20 |
| 2026-10-31 | Daily | 2026-11-01 |
| 2026-12-31 | Daily | 2027-01-01 |
| 2028-02-28 | Daily | 2028-02-29 *(leap year)* |
| 2026-12-29 | Weekly | 2027-01-05 |
| any | Once | `None` |
| complete same task twice | Daily | second call returns `None`, no extra task |

### Evaluation
| Criterion | Claude 3.5 Sonnet | GPT-4o |
|---|---|---|
| Uses `timedelta` (not manual day+1 / month math)? | *observed:* | *observed:* |
| Correct on all 8 cases above? | *observed:* | *observed:* |
| Handles `Once` / unknown frequency without crashing? | *observed:* | *observed:* |
| Prevents duplicate / double-spawn? | *observed:* | *observed:* |
| Copies all fields, resets status, new id? | *observed:* | *observed:* |
| Date-string ↔ datetime conversion correct (`strptime`/`strftime`)? | *observed:* | *observed:* |
| Code clarity / docstring / length | *observed:* | *observed:* |
| Explained assumptions or edge cases unprompted? | *observed:* | *observed:* |

### Common failure modes to look for
These are the typical ways this function goes wrong, and what the test cases above are designed to catch:
- Incrementing `day + 1` on an integer or string → breaks at month/year end.
- Using `timedelta(months=1)` (doesn't exist) or approximating a week as `days=6`/`8`.
- Mutating the original task's date instead of creating a new task (loses history).
- Spawning from a task that is already complete → duplicates on repeated clicks.
- Forgetting to reset `status` to "Pending" on the new task, or sharing the old `id`.

### Useful outputs / flaws / final decision
| | Claude 3.5 Sonnet | GPT-4o |
|---|---|---|
| Most useful part of the output | *observed:* | *observed:* |
| Flaws found | *observed:* | *observed:* |
| Changes I had to make | *observed:* | *observed:* |

**Final decision:** *(fill in which output you based `handle_recurring_task` on and why; the version in `pawpal_system.py` uses `timedelta` via a `RECURRENCE_DELTAS` lookup table, copies fields into a fresh `Task`, and guards against duplicates.)*
