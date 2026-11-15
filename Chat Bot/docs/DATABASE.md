# Astronaut Psychological Check-in System: Database Architecture

This document describes the unified database architecture for the Astronaut Psychological Daily Check-in Assistant (NASA Space Apps Challenge 2026).

---

## 1. Design Principles & Compatibility

1. **Single Database Connection (`DB_URL`)**:
   - Default: SQLite (`sqlite:///./astronaut_checkin.db`) with `check_same_thread=False` for local testing and lightweight edge operations.
   - Production / Teammate Integration: 100% compatible with PostgreSQL / MySQL via standard SQLAlchemy connection strings (e.g., `postgresql://user:pass@host:5432/dbname`).
2. **Namespace Collision Prevention (`astro_` Prefix)**:
   - Every table is prefixed with `astro_` (`astro_astronauts`, `astro_sessions`, `astro_fusion_results`, etc.).
   - This guarantees zero table-name collisions when mounted inside your teammate's existing mission control database or shared schema.
3. **Versioned Lightweight Migrations**:
   - Tracked via table `astro_migrations` (`version`, `name`, `applied_at`).
   - Automatically executes during application initialization or modular mounting via `app.migrations.runner.apply_migrations(engine)`.
4. **Strict No-Raw-Media Policy**:
   - **No audio recordings or video camera frames are ever written to disk or stored in tables.**
   - Only non-invasive numerical features (voice pitch variance, jitter/shimmer, action unit intensities, heart rate estimates, fatigue indices) and derived psychological ratings are preserved.
   - All crew check-ins comply with the non-diagnostic early-warning support tool boundary.

---

## 2. Table Organization (3 Groups)

### Group A: PEOPLE
Manages astronaut profiles, telemetry linkages, and informed consent flags.

- **`astro_astronauts`**:
  - `id` (INTEGER, Primary Key)
  - `name` (VARCHAR(120), Required)
  - `language` (VARCHAR(10), Default "en", "en" or "ar")
  - `role` (VARCHAR(80), e.g., "Commander", "Flight Engineer", "Mission Specialist")
  - `created_at` (DATETIME, UTC)
  - `external_user_id` (VARCHAR(120), Nullable, Indexed): Foreign link to teammate's user table if integrated into an existing website authentication system.
  - `consent_flag` (BOOLEAN, Default True): Indicates crew consent for psychological monitoring.
  - `is_simulated` (BOOLEAN, Default True): Explicit flag documenting whether records derive from synthetic/simulator profiles or flight crews.

---

### Group B: RESULTS
Tracks conversational telemetry, timeline events, biometric channel signals, psychological screening analyses, and longitudinal multimodal fusion.

- **`astro_sessions`**:
  - `id` (INTEGER, Primary Key)
  - `astronaut_id` (INTEGER, FK -> `astro_astronauts.id`)
  - `created_at` (DATETIME, UTC)
  - `ended_at` (DATETIME, UTC, Nullable)
  - `mission_day` (INTEGER)
  - `mode` (VARCHAR(20), "session" | "companion")
  - `status` (VARCHAR(20), "active" | "completed")
  - `question_count` (INTEGER, Default 0)
  - `pending_question` (TEXT, Nullable): Queued question held while timed crew task is active.
  - `pending_question_index` (INTEGER, Nullable)

- **`astro_messages`**:
  - `id` (INTEGER, Primary Key)
  - `session_id` (INTEGER, FK -> `astro_sessions.id`)
  - `role` (VARCHAR(20), "user" | "assistant")
  - `content` (TEXT)
  - `mode` (VARCHAR(20), "session" | "companion")
  - `created_at` (DATETIME, UTC)

- **`astro_task_events`**:
  - `id` (INTEGER, Primary Key)
  - `session_id` (INTEGER, FK -> `astro_sessions.id`)
  - `task` (VARCHAR(100), e.g., "Reaction Time Test", "Docking Simulator", "EVA Maintenance")
  - `phase` (VARCHAR(50), "started" | "ended")
  - `ts` (DATETIME, UTC)
  - `info_json` (TEXT, JSON payload of duration, score, or metadata)

- **`astro_signals`**:
  - `id` (INTEGER, Primary Key)
  - `session_id` (INTEGER, FK -> `astro_sessions.id`)
  - `channel` (VARCHAR(50), "acoustic" | "facial" | "physiological" | "multimodal")
  - `signals_json` (TEXT, JSON dictionary of numerical biometric features)
  - `quality` (FLOAT, 0.0 - 1.0 confidence/quality metric)
  - `ts` (DATETIME, UTC)

- **`astro_analyses`**:
  - `id` (INTEGER, Primary Key)
  - `session_id` (INTEGER, FK -> `astro_sessions.id`, Unique)
  - `scores_json` (TEXT, JSON dictionary of 6 dimensions: stress, low_mood, anxiety, fatigue, social_isolation, concentration_difficulty, rated 0-10)
  - `evidence_json` (TEXT, JSON dictionary of clinical reasoning quotes)
  - `screening_answers_json` (TEXT, JSON of structured screening answers)
  - `confidence` (FLOAT, 0.0 - 1.0)
  - `risk_flag` (BOOLEAN, True if acute risk or flight surgeon escalation needed)
  - `notes` (TEXT, Clinical summary)
  - `created_at` (DATETIME, UTC)

- **`astro_fusion_results`**:
  - `id` (INTEGER, Primary Key)
  - `session_id` (INTEGER, FK -> `astro_sessions.id`, Unique)
  - `astronaut_id` (INTEGER, FK -> `astro_astronauts.id`)
  - `fused_scores_json` (TEXT, JSON dictionary of weighted multi-channel fused scores)
  - `composite_score` (FLOAT, Weighted composite operational strain index 0.0 - 10.0)
  - `z_scores_json` (TEXT, JSON dictionary of standard deviations from personal baseline)
  - `channel_conflict` (BOOLEAN, True if verbal report conflicts with biometric telemetry)
  - `conflict_notes` (TEXT, Explanation of observed discordance)
  - `baseline_confidence` (VARCHAR(20), "low" if <5 past sessions, "high" if >=5 sessions)
  - `alert_triggered` (BOOLEAN, Persistent deviation alert flag)
  - `created_at` (DATETIME, UTC)

- **`astro_baselines`**:
  - `id` (INTEGER, Primary Key)
  - `astronaut_id` (INTEGER, FK -> `astro_astronauts.id`)
  - `dimension` (VARCHAR(50), Unique per astronaut)
  - `mean` (FLOAT)
  - `std` (FLOAT)
  - `n` (INTEGER, Number of calibration sessions)
  - `updated_at` (DATETIME, UTC)

- **`astro_alerts`**:
  - `id` (INTEGER, Primary Key)
  - `session_id` (INTEGER, FK -> `astro_sessions.id`)
  - `reason` (TEXT)
  - `source` (VARCHAR(20), "chat" | "analysis" | "keyword" | "fusion")
  - `handled` (BOOLEAN, Default False)
  - `created_at` (DATETIME, UTC)

- **`astro_kb_usage`**:
  - `id` (INTEGER, Primary Key)
  - `message_id` (INTEGER, FK -> `astro_messages.id`)
  - `chunk_id` (INTEGER, FK -> `astro_kb_chunks.id`)
  - `created_at` (DATETIME, UTC)

---

### Group C: KNOWLEDGE
Curated, reviewed operational protocols for spaceflight psychological support.

- **`astro_kb_chunks`**:
  - `id` (INTEGER, Primary Key)
  - `title` (VARCHAR(255), Title of protocol)
  - `topic` (VARCHAR(50), e.g., "sleep", "stress", "anxiety", "fatigue", "isolation", "mood", "focus", "escalation")
  - `severity_min` (FLOAT, 0.0 - 10.0)
  - `severity_max` (FLOAT, 0.0 - 10.0)
  - `content` (TEXT, Operational intervention / protocol text)
  - `source_name` (VARCHAR(255), e.g., "NASA Behavioral Health Guidelines")
  - `source_url` (VARCHAR(512))
  - `language` (VARCHAR(10), "en" or "ar")
  - `last_reviewed` (DATETIME, UTC)
  - `approved` (BOOLEAN, Default False, indexed; only approved chunks are used by the chatbot)

- **`astro_kb_chunks_fts` (SQLite FTS5 Virtual Table)**:
  - High-speed BM25 indexed virtual table synchronizing with `astro_kb_chunks` via database triggers (`astro_kb_chunks_ai`, `astro_kb_chunks_ad`, `astro_kb_chunks_au`).

---

## 3. Entity-Relationship Diagram

```mermaid
erDiagram
    astro_astronauts ||--o{ astro_sessions : "participates in"
    astro_astronauts ||--o{ astro_baselines : "has calibrated"
    astro_astronauts ||--o{ astro_fusion_results : "evaluated across"

    astro_sessions ||--o{ astro_messages : "contains"
    astro_sessions ||--o{ astro_task_events : "logs timeline"
    astro_sessions ||--o{ astro_signals : "receives telemetry"
    astro_sessions ||--o| astro_analyses : "yields"
    astro_sessions ||--o| astro_fusion_results : "fused into"
    astro_sessions ||--o{ astro_alerts : "generates"

    astro_messages ||--o{ astro_kb_usage : "references"
    astro_kb_chunks ||--o{ astro_kb_usage : "used in"

    astro_astronauts {
        int id PK
        string name
        string language
        string role
        datetime created_at
        string external_user_id
        boolean consent_flag
        boolean is_simulated
    }

    astro_sessions {
        int id PK
        int astronaut_id FK
        datetime created_at
        datetime ended_at
        int mission_day
        string mode
        string status
        int question_count
        text pending_question
        int pending_question_index
    }

    astro_messages {
        int id PK
        int session_id FK
        string role
        text content
        string mode
        datetime created_at
    }

    astro_task_events {
        int id PK
        int session_id FK
        string task
        string phase
        datetime ts
        text info_json
    }

    astro_signals {
        int id PK
        int session_id FK
        string channel
        text signals_json
        float quality
        datetime ts
    }

    astro_analyses {
        int id PK
        int session_id FK
        text scores_json
        text evidence_json
        text screening_answers_json
        float confidence
        boolean risk_flag
        text notes
        datetime created_at
    }

    astro_fusion_results {
        int id PK
        int session_id FK
        int astronaut_id FK
        text fused_scores_json
        float composite_score
        text z_scores_json
        boolean channel_conflict
        text conflict_notes
        string baseline_confidence
        boolean alert_triggered
        datetime created_at
    }

    astro_baselines {
        int id PK
        int astronaut_id FK
        string dimension
        float mean
        float std
        int n
        datetime updated_at
    }

    astro_alerts {
        int id PK
        int session_id FK
        text reason
        string source
        boolean handled
        datetime created_at
    }

    astro_kb_chunks {
        int id PK
        string title
        string topic
        float severity_min
        float severity_max
        text content
        string source_name
        string source_url
        string language
        datetime last_reviewed
        boolean approved
    }

    astro_kb_usage {
        int id PK
        int message_id FK
        int chunk_id FK
        datetime created_at
    }
```

---

## 4. Teammate Dashboard Endpoints

The database is exposed to frontend dashboards via the following endpoints:

| Endpoint | Method | Purpose | Source Table |
|---|---|---|---|
| `/astronauts/{id}/history` | GET | Longitudinal check-in history, scores & fusion | `astro_sessions`, `astro_analyses`, `astro_fusion_results` |
| `/dashboard/fused-latest` | GET | Latest multimodal fused composite scores per astronaut | `astro_fusion_results`, `astro_astronauts` |
| `/dashboard/alerts` | GET | Active and unhandled clinical / fusion alerts | `astro_alerts`, `astro_sessions` |
| `/dashboard/kb-usage` | GET | Protocols and coping strategies referenced during sessions | `astro_kb_usage`, `astro_kb_chunks`, `astro_messages` |

---

## 5. Seeding & Knowledge Base Loading

- **Database Initialization & Seeding**:
  ```bash
  python seed.py
  ```
  Runs versioned migrations, loads approved placeholder protocols from `data/kb_seed_placeholder.json`, creates demo astronauts (Dr. Sarah Al-Mansoor & Omar Al-Farooq), baseline calibrations, and sample completed sessions with task events and fusion results.

- **Selective Knowledge Base Loading**:
  ```bash
  python -m scripts.kb_load
  ```
  Strictly verifies `approved=True` on each chunk before loading. Any unapproved or work-in-progress content is safely excluded from model retrieval.
