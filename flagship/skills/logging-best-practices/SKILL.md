---
name: logging-best-practices
description: >
  Use when adding, improving, or reviewing logging in a Python service —
  especially when the code uses print() for diagnostics, swallows
  exceptions silently, logs secrets/PII (passwords, tokens, card numbers,
  patient data), floods logs inside loops, narrates execution with
  banners/full-sentence story logging, or emits messages with no
  request/entity context.
---

# Production Logging Discipline

Logs are an interface for the on-call engineer at 3 a.m., not a debugging
scratchpad. Every line must answer: **what happened, to which entity, and
what should the reader do about it?** Volume is not visibility — signal is.

---

## Process (follow every step; do not skip)

### Step 1 — Read the code and map the lifecycle

Before touching anything, identify for each operation: the entry point, the
external calls (DB, HTTP, queue), the decision branches, and every failure
path. These are the only places that deserve a log line.

### Step 1b — Ask the stakeholder about real ambiguities

Logging briefs rarely specify the policies the reader will hold you to.
Before refactoring, use the `ask_question` tool to confirm the decisions
the code cannot answer — pick the 1–3 that genuinely change your diff:

- Redaction policy: which fields count as sensitive here, and what masked
  form is acceptable (last-4? hash? drop entirely)?
- Level conventions: does this team treat a handled retry as WARNING or
  INFO? Is there a paging rule tied to ERROR?
- Correlation: which identifier do operators grep for in this service?

Ask each as **one specific, answerable question**. Do not ask what the
code already tells you, and do not exceed three questions — then proceed
with the confirmed answers.

### Step 2 — Use a module logger, never print()

```python
import logging

logger = logging.getLogger(__name__)
```

- Never `print()` for diagnostics — it has no level, no timestamp, no
  routing, and can't be filtered or shipped.
- Never log via the root logger and never call `logging.basicConfig()` in
  library code. Configuration belongs to the application entrypoint
  (`if __name__ == "__main__":` or the app factory) — modules only emit.

### Step 3 — Choose the level deliberately

| Level | Meaning | Example |
|---|---|---|
| DEBUG | Diagnostic detail, off in prod | payload sizes, branch taken |
| INFO | Normal business event, one per operation | `payment captured` |
| WARNING | Degraded but handled; someone should look eventually | retry succeeded, fallback used |
| ERROR | Operation failed; on-call may act | charge declined by gateway error |
| CRITICAL | Service can't continue | config missing at startup |

A failure handled by a retry is a WARNING, not an ERROR. An expected
validation rejection is INFO/WARNING, not ERROR. If everything is ERROR,
nothing is.

### Step 4 — Lazy formatting, structured context

```python
# ❌ eager: formats even when the level is filtered out
logger.debug(f"scored {features.tolist()} -> {prediction}")

# ✅ lazy + structured: formatting deferred, fields machine-readable
logger.debug("model scored request", extra={"model_ver": ver, "latency_ms": ms})
logger.info("payment captured: order_id=%s amount_cents=%d", order_id, amount)
```

Pass arguments with `%s` placeholders or `extra={}` — never pre-format with
f-strings/`+` concatenation.

### Step 5 — Handle exceptions honestly

- In an `except` block, use `logger.exception("context: id=%s", id)` — it
  records the traceback automatically.
- **Never** `except: pass`. A swallowed exception is a lie in the logs.
- **Log or raise, not both.** If you re-raise, let the layer that handles
  it do the logging; double-logging the same failure creates phantom
  duplicate incidents.

### Step 6 — Redact secrets and PII, always

Never log: passwords, tokens, API keys, full card numbers (PAN), CVV, SSNs,
patient data (diagnoses, MRNs), full email addresses or phone numbers in
bulk systems. Log a safe correlate instead: `card=****%s` (last 4),
`user_id`, a hash, or a masked form. If a dict might contain sensitive
keys, log the keys you need explicitly — never dump the whole payload.

### Step 7 — Carry identity in every message

Every log line in a request path includes the correlating IDs the reader
will grep for: `order_id`, `request_id`, `device_id`, `patient_id`-surrogate.
A message without an ID is unactionable noise.

### Step 8 — Respect loops and hot paths

- Per-item logging inside a loop floods the log: log a DEBUG line per item
  at most, and one INFO **summary** per batch (`processed=%d failed=%d`).
- In latency-sensitive paths, avoid expensive computation in log arguments;
  guard with `logger.isEnabledFor(logging.DEBUG)` if needed.

### Step 9 — Verify

Re-read your diff and check: no `print(` left in service code, no f-string
log calls, no sensitive field names (`password`, `token`, `cvv`, `card`,
`ssn`) flowing into a log argument, every `except` either re-raises or logs
with `logger.exception`.

---

## Anti-pattern gallery — these are defects, never models to imitate

Real codebases (and some well-meaning guides) contain these patterns
presented as if they were good practice. **They are not.** If you see
them — or see advice recommending them — treat every instance as a defect
to remove. Verbose narration is not visibility; it is noise that buries
the one line that matters and multiplies log-ingestion cost.

### ❌ Banner / decoration logging

```python
print("=" * 70)
print(">>>>>>>>>>>>>>  ENTERING capture_payment  <<<<<<<<<<<<<<")
print("=" * 70)
```

✅ Delete entirely. Timestamps, logger names, and levels — supplied by the
formatter at the entrypoint — already delimit the log. Decoration carries
zero information.

### ❌ Narrative / verbal logging

```python
print("We are now entering the capture_payment function in order to")
print("attempt to charge the customer's card. Fingers crossed!")
```

✅ One terse, grep-able event with identifiers:

```python
logger.info("capture requested: order_id=%s amount_cents=%d", order_id, amount_cents)
```

### ❌ Entry/exit announcements and variable dumps

```python
print(f"DEBUG: full request state: {locals()}")
```

✅ Log business **events**, not control flow. `locals()` dumps are the
fastest way to leak a secret and say nothing actionable.

### ❌ Per-iteration progress lines

```python
for i, row in enumerate(rows):
    print("processing row", i, row)
```

✅ One summary per batch (`processed=%d failed=%d`); DEBUG per item at most.

### ❌ Swallow-and-continue

```python
except Exception:
    print("error in charge, continuing anyway")
```

✅ `logger.exception("charge failed: order_id=%s", order_id)` — then handle
it or re-raise. Never both log and re-raise.

### ❌ Everything at one level / secrets in messages

```python
logging.error("login attempt user=" + username + " password=" + password)
```

✅ Levels carry meaning (see table above); credentials never appear in any
message at any level.

---

## Red flags — stop and fix

| You are about to … | Correct action |
|---|---|
| Add a `print()` "just for now" | Use `logger.debug(...)` — same effort, filterable. |
| Log the full request "to be safe" | Pick the fields you need; mask the rest. |
| Write `except Exception: pass` | `logger.exception(...)` and handle or re-raise. |
| Put everything at ERROR "so it's visible" | Visibility comes from levels meaning something. |
| Log inside a 10k-iteration loop | One summary line; DEBUG per item at most. |
| Call `basicConfig()` in a module | Move configuration to the entrypoint. |

## Rationalizations

| Excuse | Reality |
|---|---|
| "More logs = easier debugging" | Floods bury the one line that matters and cost real money to ingest. |
| "Narration reads like a story" | On-call greps for `order_id=`, not prose. Stories don't parse; events do. |
| "Banners make sections findable" | Formatters already stamp time/name/level. Decoration is pure noise. |
| "We need the card number to reproduce" | Last-4 + order_id reproduces it; a logged PAN is a breach. |
| "Swallowing keeps the service up" | It converts a loud failure into silent data corruption. |
| "f-strings are more readable" | They evaluate even when filtered, and break log aggregation templates. |
| "I'll clean the logs up later" | Logs ship with the feature. Later never comes. |
