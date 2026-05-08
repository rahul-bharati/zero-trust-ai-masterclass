# Zero-Trust AI — SQL Agent Demo

> **"You don't need to be a security expert to build a Zero-Trust AI agent. You just need to stop trusting the LLM. That's the entire mindset shift. Everything else is plumbing."**

**Author:** Rahul Bharati

**Prepared for:** Beyond the Happy Path: Engineering Zero-Trust AI Agents

---

## Project Summary

A phased, end-to-end demo of a Zero-Trust SQL agent built on top of a deliberately vulnerable database.

| Phase | Branch | What it builds |
|---|---|---|
| 1 | `phase-1-sql-executor` | Vulnerable base app — raw SQL over a sensitive SQLite DB |
| 2 | `phase-2-naive-agent` | Naive LLM agent — Claude via LiteLLM, natural language → SQL |
| 3 | `phase-3-zero-trust` | Zero-Trust pipeline — bidirectional guard model wrapping Claude |

Each phase has its own README in its own branch with the full details for that stage.

**Stack:** FastAPI · Streamlit · SQLite · Faker · LiteLLM · Ollama

---

## Key Pointers

### The Core Idea

In traditional web security, Zero Trust means:

> *Never trust, always verify — regardless of where a request comes from.*

Applied to AI agents:

> *The LLM is a powerful but untrustworthy executor. It must never be the last line of defence.*

The architecture that enforces this is a **bidirectional guard model** — a second, smaller model whose only job is to be suspicious:

```
User → [GUARD: input] → LLM → SQL → DB → Rows → [GUARD: output] → User
         ↓ blocks if risky                         ↓ blocks/redacts if leaky
```

The input guard never sees the schema — it can't be tricked into helping write an attack because it doesn't know what to attack. It only knows how to recognise hostile intent. The output guard catches what the input guard missed: innocent-looking prompts that happen to surface dangerous data.

The guard model does not need to be large or sophisticated. It needs to be **suspicious** — which is a much smaller skill than intelligence. The right model for this role depends on the complexity of your rule set; simpler heuristics run fine on lightweight models, but nuanced intent detection and adversarial framing benefit from a more capable one.

> *"We're not making the guard smart. We're making it paranoid. Suspicion is a smaller skill than intelligence."*

### Why It Matters

LLMs connected to live databases can:

- **Leak PII** in response to an innocent-looking question — no malice required
- **Be injected** via crafted user input that overrides the system prompt
- **Execute destructive SQL** (`DELETE`, `DROP`) from an ambiguous phrase like *"clean up old test data"*
- **Expose the full schema** to a reconnaissance query
- **Cross tenant boundaries** because the model has no concept of the authenticated user's scope

None of these are bugs in the model. **The bug is in the architecture** — in the assumption that a capable enough model and a long enough prompt is a substitute for a real trust boundary.

> *"Claude isn't malfunctioning. Claude is doing exactly what we asked. The bug isn't in the model. The bug is in our trust assumptions."*

### The Analogy

This is not a new idea. The pattern is decades old:

| Domain | Mechanism | Age |
|---|---|---|
| HTTP traffic | Web Application Firewalls (WAF) | ~25 years |
| Email | Spam filters + DLP scanners | ~30 years |
| Executable files | Antivirus heuristics | ~40 years |
| AI agent output | Zero-Trust guard model | *Now* |

> *"Zero-Trust AI isn't a new idea. It's a 30-year-old idea applied to a new attack surface."*

The vocabulary is missing, there's no OWASP equivalent yet, and most tutorials are written by people building toys rather than production systems. That's the gap this project addresses.

---

## Phase 1 — The Vulnerable Base App

**Branch:** `phase-1-sql-executor`

### Goal

Build a working app that embodies the anti-patterns most commonly found in early-stage production systems. This is the **"before" picture** — no LLM yet, just raw SQL execution through a web UI, to establish that the data exposure problem exists independently of AI.

Phase 2 adds natural language input on top of this same stack.

---

### Stack

| Layer | Technology | Why |
|---|---|---|
| Backend | FastAPI | Lightweight, async, easy to run and inspect |
| Frontend | Streamlit | Rapid UI prototyping |
| Database | SQLite | Zero setup, single file, easily re-seeded |
| Seed data | Faker (`en_IN`) | Realistic Indian names, addresses, phone numbers |

---

### Database Schema

The schema is **deliberately over-privileged**. Every sensitive field that should never share a table is here in one table. This mirrors what real prototypes look like.

#### `users` — The Goldmine

```sql
CREATE TABLE users (
                       id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                       full_name          TEXT,
                       email              TEXT,
                       date_of_birth      TEXT,
                       age                INTEGER,
                       phone              TEXT,
                       address            TEXT,
                       aadhaar_number     TEXT,           -- masked format: XXXX-XXXX-NNNN
                       password_plaintext TEXT,           -- yes, plaintext. this is intentional.
                       password_hash      TEXT,           -- SHA-256, for the illusion of security
                       salary             INTEGER,        -- INR
                       credit_card_number TEXT,
                       medical_notes      TEXT,
                       created_at         TEXT
);
```

`password_plaintext` exists because storing plaintext passwords is a pattern that appears in real production systems more often than it should.
Aadhaar is used as the national ID equivalent; comparable to SSN in sensitivity and regulatory weight.
**Seed:** 300 rows — enough that `SELECT * FROM users` returns every sensitive field across the full user base in a single query.

#### `orders` — The Transaction Trail

```sql
CREATE TABLE orders (
                        id         INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id    INTEGER,
                        amount     REAL,
                        item       TEXT,
                        created_at TEXT,
                        FOREIGN KEY(user_id) REFERENCES users(id)
);
```

**Seed:** 500 rows linked to random users. Used in Phase 2 to demonstrate cross-tenant access and aggregation leaks.

#### `internal_notes` — The Operational Secrets

```sql
CREATE TABLE internal_notes (
                                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                                user_id INTEGER,
                                note    TEXT,
                                FOREIGN KEY(user_id) REFERENCES users(id)
);
```

Sample seeded notes:
- *"VIP customer, do not refund under any circumstances."*
- *"Flagged for potential fraud investigation."*
- *"CEO's friend, apply 50% discount automatically."*
- *"Owes us money, block next transaction."*

**Seed:** 20 rows — small enough to be hidden in noise, damaging enough to be a serious leak.

---

### Files

| File | Role |
|---|---|
| `database.py` | Schema definition + Faker seed script |
| `main.py` | FastAPI backend — raw SQL executor |
| `app.py` | Streamlit frontend |
| `requirements.txt` | All dependencies, pinned |
| `vulnerable_app.db` | SQLite database (generated by `database.py`) |

#### `database.py`

Creates all three tables (dropping and recreating on each run for a clean state), then seeds 300 users, 500 orders, and 20 internal notes using Faker's `en_IN` locale.

#### `main.py`

Single `POST /execute` endpoint. Accepts a raw SQL string and runs it directly — **zero validation, zero sanitisation, zero allow-listing**. SELECTs return rows as JSON; writes commit and return `rows_affected`. Errors are surfaced to the caller (intentional — error messages are useful for schema reconnaissance).

The deliberately insecure line:
```python
# Deliberately insecure: direct execution of incoming string
cursor.execute(query)
```

This is the line that Phase 3 makes safe — not by changing it, but by wrapping the whole pipeline in trust boundaries before it is ever reached.

#### `app.py`

Single SQL input + `Run Query` button. Displays the exact SQL executed above the results, alongside a full-width interactive DataFrame and a row count.

---

### Running Phase 1

```bash
# Install dependencies
pip install -r requirements.txt

# Seed the database
python database.py

# Terminal 1 — FastAPI backend
uvicorn main:app --reload

# Terminal 2 — Streamlit frontend
streamlit run app.py
```

Open `http://localhost:8501`.

---

### Sample Queries

| Query | What it returns |
|---|---|
| `SELECT * FROM users LIMIT 10` | Every column including passwords and Aadhaar |
| `SELECT full_name, email, aadhaar_number, credit_card_number FROM users` | Targeted PII dump |
| `SELECT full_name, salary, medical_notes FROM users ORDER BY salary DESC` | Salary and health data together |
| `SELECT u.full_name, o.amount, o.item FROM users u JOIN orders o ON u.id = o.user_id LIMIT 20` | Cross-table PII join |
| `SELECT u.full_name, n.note FROM users u JOIN internal_notes n ON u.id = n.user_id` | Internal operational notes |
| `PRAGMA table_info(users)` | Schema reconnaissance — full column list |
| `DELETE FROM orders WHERE created_at < '2024-01-01'` | Destructive write with no confirmation |

---

### What Phase 1 Deliberately Omits

These absences are intentional — they are the setup for Phase 2:

- ❌ No authentication
- ❌ No authorisation or row-level scoping
- ❌ No input validation or SQL sanitisation
- ❌ No column allow-listing
- ❌ No rate limiting
- ❌ No audit logging

---

### What Phase 1 Sets Up

Phase 1 establishes the attack surface. Every gap above gets exploited in Phase 2 — not by a hacker, but **by the LLM**, doing exactly what it was asked in natural language.

Phase 2 surfaces the core architectural question: how do you add safety to a system where the LLM itself is the untrusted component? Adding more constraints to the prompt is insufficient — the next phase introduces a second model whose only job is to evaluate inputs and outputs independently.

That architecture is Phase 3.

---

*Built as a live conference demo. The vulnerability is the point.*
