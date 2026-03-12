# Enwealth E-Board Portal

<p align="center">
  <img src="static/images/logo.png" alt="Enwealth Logo" width="180"/>
</p>

<p align="center">
  <strong>A secure, full-featured digital board governance platform for multi-branch organizations.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Django-5.x-green?logo=django" />
  <img src="https://img.shields.io/badge/Python-3.12+-blue?logo=python" />
  <img src="https://img.shields.io/badge/PostgreSQL-15+-blue?logo=postgresql" />
  <img src="https://img.shields.io/badge/Celery-5.3+-brightgreen?logo=celery" />
  <img src="https://img.shields.io/badge/Redis-7+-red?logo=redis" />
  <img src="https://img.shields.io/badge/License-Proprietary-lightgrey" />
</p>

---

## Table of Contents

1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Architecture](#architecture)
4. [Tech Stack](#tech-stack)
5. [Project Structure](#project-structure)
6. [Apps & Modules](#apps--modules)
   - [Accounts](#accounts)
   - [Agencies](#agencies)
   - [Dashboard](#dashboard)
   - [Meetings](#meetings)
   - [Documents](#documents)
   - [E-Signature](#e-signature)
   - [Voting](#voting)
   - [Risk Management](#risk-management)
   - [Policy](#policy)
   - [Evaluation](#evaluation)
   - [Discussions](#discussions)
   - [Notifications](#notifications)
   - [Audit](#audit)
   - [Analytics](#analytics)
7. [Getting Started](#getting-started)
   - [Prerequisites](#prerequisites)
   - [Installation](#installation)
   - [Environment Variables](#environment-variables)
   - [Database Setup](#database-setup)
   - [Running the Development Server](#running-the-development-server)
   - [Running Celery Workers](#running-celery-workers)
8. [User Roles & Permissions](#user-roles--permissions)
9. [Multi-Timezone Support](#multi-timezone-support)
10. [E-Signature Workflow](#e-signature-workflow)
11. [Security](#security)
12. [API](#api)
13. [Deployment](#deployment)
14. [Contributing](#contributing)
15. [License](#license)

---

## Overview

**Enwealth E-Board Portal** is an enterprise-grade digital governance platform designed for Enwealth's multi-branch, multi-country organizational structure. It brings together every aspect of board governance — from scheduling meetings and managing documents, to electronic signing, risk management, policy lifecycle, board evaluations, and secure communications — into a single, secure, role-controlled web application.

The platform is purpose-built for organizations operating across **Kenya, Uganda, Mauritius, and other African and international markets**, with first-class support for per-user timezone rendering, multi-branch access control, and a complete electronic signature workflow that is legally traceable.

---

## Key Features

| Area | Highlights |
|---|---|
| **Authentication & MFA** | Email-based login, TOTP multi-factor authentication (django-otp), role-based access control, session expiry, rate limiting |
| **Multi-Branch Governance** | Organizations → Branches (with hierarchy) → Committees; per-branch roles, unlimited depth, quorum tracking |
| **Board Meetings** | Full meeting lifecycle, agenda, minutes, attendance, action items, quorum enforcement, virtual platform links (Zoom, Teams, Meet, etc.) |
| **Document Management** | Upload, version, tag, share, comment on governance documents with fine-grained access control |
| **Electronic Signatures** | End-to-end PDF signing: upload → assign signers (internal & external) → OTP verification → capture signature (draw / type / upload) → finalization with SHA-256 audit hash; full audit trail |
| **Voting & Resolutions** | Motions lifecycle (draft → proposed → debate → voting → result), multiple voting types (simple majority, qualified, two-thirds, unanimous), anonymous voting option, auto-close expired resolutions |
| **Risk Management** | Risk register with categorisation, probability/impact scoring, heat-map ready data, treatment plans, review cycles |
| **Policy Management** | Policy lifecycle (draft → review → approved → published → archived), version history, category hierarchy |
| **Board Evaluation** | Configurable evaluation templates, assigned evaluation cycles, individual responses, aggregate scoring |
| **Discussions** | Threaded forum-style discussions with forum types, access levels, mentions, pinning, and rich content |
| **Notifications** | Real-time in-app notifications with type classification (meeting, voting, document, risk, security, etc.), priority levels, read/unread tracking |
| **Audit Trail** | Immutable audit log for all critical actions across every module |
| **Analytics** | Participation, attendance, voting trend, and engagement analytics dashboards |
| **Timezone Awareness** | Per-user preferred timezone; meetings and events rendered in local time; timezone notice when user differs from branch timezone |
| **Celery Background Tasks** | Async email sending, meeting reminders, document finalization, OTP delivery, auto-close resolutions, database backups |

---

## Architecture

```
/dev/null/diagram.txt#L1-18
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (HTMX + Alpine.js + Tailwind)    │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP / WebSocket
┌───────────────────────────▼─────────────────────────────────────┐
│               Django 5.x  (Gunicorn / WSGI)                     │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ ┌────────────────┐  │
│  │ Accounts │ │ Agencies │ │  Meetings   │ │  E-Signature   │  │
│  │  + MFA   │ │ + Branches│ │ + Agenda    │ │  + PDF Service │  │
│  └──────────┘ └──────────┘ └─────────────┘ └────────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ ┌────────────────┐  │
│  │  Voting  │ │   Risk   │ │   Policy    │ │   Evaluation   │  │
│  └──────────┘ └──────────┘ └─────────────┘ └────────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ ┌────────────────┐  │
│  │   Docs   │ │  Audit   │ │  Discuss.   │ │  Notifications │  │
│  └──────────┘ └──────────┘ └─────────────┘ └────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
              ┌─────────────┼─────────────────┐
    ┌─────────▼──────┐ ┌────▼─────┐ ┌─────────▼──────┐
    │  PostgreSQL 15  │ │  Redis   │ │   File Storage  │
    │  (primary DB)   │ │  (broker │ │  (media / PDFs) │
    └────────────────┘ │  + cache)│ └─────────────────┘
                       └──────────┘
                            │
                   ┌────────▼────────┐
                   │  Celery Workers │
                   │  + Celery Beat  │
                   └─────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.12+ |
| **Framework** | Django 5.x |
| **Database** | PostgreSQL 15+ |
| **Cache / Message Broker** | Redis 7+ |
| **Task Queue** | Celery 5.3 + django-celery-beat |
| **Frontend** | HTMX, Alpine.js, Tailwind CSS (via CDN / CLI) |
| **Forms** | django-crispy-forms + crispy-tailwind |
| **MFA / OTP** | django-otp (TOTP), custom email OTP |
| **PDF Generation** | ReportLab |
| **File Validation** | python-magic |
| **Image Processing** | Pillow |
| **Static Files** | WhiteNoise |
| **REST API** | Django REST Framework |
| **WSGI Server** | Gunicorn |
| **Config Management** | python-decouple (.env files) |
| **Rate Limiting** | django-ratelimit |

---

## Project Structure

```
/dev/null/tree.txt#L1-50
Enwealth/
├── apps/
│   ├── accounts/          # Custom user model, auth, MFA, roles, permissions
│   ├── agencies/          # Organizations, branches, committees, memberships, invitations
│   ├── analytics/         # Dashboards, participation & voting analytics
│   ├── audit/             # Immutable audit log across all modules
│   ├── board_evaluation/  # Legacy evaluation scaffold (superseded by apps/evaluation)
│   ├── dashboard/         # Landing dashboard views
│   ├── discussions/       # Threaded board forums & comments
│   ├── documents/         # Document upload, versioning, sharing, comments
│   ├── esignature/        # Full e-signing workflow (upload → assign → sign → finalize)
│   ├── evaluation/        # Configurable evaluation templates & cycles
│   ├── meetings/          # Meeting scheduling, agenda, minutes, attendance, actions
│   ├── notifications/     # In-app notification engine
│   ├── policy/            # Policy lifecycle management
│   ├── risk/              # Risk register, scoring, treatment plans
│   └── voting/            # Motions, voting rounds, results
├── config/
│   ├── settings/
│   │   ├── base.py        # Shared settings
│   │   ├── development.py # Dev overrides (DEBUG=True, dev CSRF cookie, etc.)
│   │   └── production.py  # Production overrides
│   ├── celery.py          # Celery app configuration
│   ├── urls.py            # Root URL configuration
│   ├── wsgi.py
│   └── asgi.py
├── templates/             # Project-wide HTML templates (per-app subdirectories)
├── static/                # Static assets (CSS, JS, images)
├── media/                 # User-uploaded files (not tracked in git)
├── logs/                  # Application logs (not tracked in git)
├── requirements/
│   ├── base.txt           # Core dependencies
│   ├── development.txt    # Dev-only (debug toolbar, etc.)
│   └── production.txt     # Production-only (sentry, etc.)
├── manage.py
└── .env.example           # Template for required environment variables
```

---

## Apps & Modules

### Accounts

**Path:** `apps/accounts/`

The foundation of the platform. Implements a fully custom Django user model using email (not username) as the primary identifier.

**Models:**
- `User` — UUID primary key, email login, role-based (`board_member`, `company_secretary`, `executive_management`, `compliance_officer`, `it_administrator`, `internal_audit`), MFA flag, preferred timezone, profile photo, department, job title.
- `PasswordHistory` — Prevents reuse of recent passwords.

**Key features:**
- Custom `CustomUserManager` with `create_user` / `create_superuser`
- TOTP-based Multi-Factor Authentication via `django-otp`
- Role-based permission decorators and mixins (`apps/accounts/decorators.py`, `mixins.py`, `permissions.py`)
- Enhanced custom admin site (`enhanced_admin.py`) with separate URL at `/admin/`
- Context processor (`context_processors.py`) that injects user permissions into every template
- Custom CSRF failure view (`csrf_failure_view.py`)
- Safe GET/POST logout with CSRF exemption (`custom_logout.py`)
- Timezone template tags (`templatetags/tz_tags.py`) — `localtime`, `tz_abbr`, `meeting_time`, `meeting_time_range`, `user_timezone_label`, `timezone_notice`

---

### Agencies

**Path:** `apps/agencies/`

Manages the multi-entity structure of the organization.

**Models:**
- `Organization` — Top-level legal entity; holds branches, logo, country, contacts.
- `Branch` — A regional office, subsidiary, or country entity. Supports unlimited parent-child hierarchy (`parent_branch` self-FK). Has a `get_hierarchy_path()` method returning ancestors list (root-first) for breadcrumb rendering. IANA timezone field.
- `Committee` — Governance committee within a branch (Board of Directors, Audit, Risk, Finance, etc.). Supports quorum calculation, sub-committees, chairperson and secretary FKs.
- `CommitteeMembership` — User ↔ Committee with role (chairperson, secretary, member, observer, etc.), term management, voting rights.
- `UserBranchMembership` — User ↔ Branch with branch-level role and access level. Primary access control layer.
- `BranchInvitation` — Token-based email invitations for onboarding users to branches.

**Branch Types:** Headquarters, Regional Office, Country Office, Subsidiary, Affiliate, Joint Venture, Representative Office.

**Committee Types:** Board of Directors, Executive, Audit, Risk & Compliance, Finance, Remuneration, Nomination, Investment, Strategy, Governance, Technical, Special/Ad-hoc, Subsidiary Board.

---

### Dashboard

**Path:** `apps/dashboard/`

The main landing page after login. Aggregates summary widgets across meetings, documents, votings, notifications, and risk alerts relevant to the authenticated user's branches and role.

---

### Meetings

**Path:** `apps/meetings/`

Full meeting lifecycle management.

**Models:**
- `Meeting` — UUID PK, title, type (Board, Committee, AGM, Emergency, Workshop, EGM), status (Scheduled, In Progress, Completed, Cancelled, Postponed), scheduled date/time, location, virtual platform (Zoom, Teams, Meet, Webex, Skype, Jitsi, Whereby), agenda, minutes, quorum status, reference number.
- `MeetingAttendance` — Tracks each invited member's attendance status (attending, declined, tentative, attended, absent).
- `AgendaItem` — Ordered agenda items with presenter, duration, attachments, status.
- `MeetingDocument` — Documents attached to a meeting.
- `MeetingAction` — Action items arising from meetings with assignee, due date, and completion status.
- `VideoConferenceParticipant` — Logs virtual attendees.
- `VideoConferenceRecording` — Links to recordings of virtual sessions.

**Timezone support:** Meeting datetimes are stored UTC-aware. Templates use `tz_tags` to render them in the logged-in user's preferred timezone, with a notice banner if the user's timezone differs from the branch timezone.

---

### Documents

**Path:** `apps/documents/`

Governance document repository.

**Models:**
- `Document` — File upload, version, category, access level, tags, status (draft, review, approved, published, archived).
- `DocumentComment` — Threaded comments on documents.
- `DocumentShare` — Controlled sharing of a document to specific users.
- `DocumentTag` — Tagging for search and filtering.

---

### E-Signature

**Path:** `apps/esignature/`

A complete, legally traceable electronic document signing workflow.

**Models:**
- `SignableDocument` — The PDF to be signed. Stores original file, original SHA-256 hash, signed file, signed SHA-256 hash, status (draft → pending → in_progress → fully_signed / rejected / expired / cancelled), expiry, ordered-signing flag, OTP requirement, access level, branch context, auto-generated reference (`ESIG-YYYY-NNNNN`).
- `SignerAssignment` — One row per (document, signer). Supports internal users and external signers (name + email only). Tracks signing order, role (signer, approver, witness, cc), status (pending → notified → viewed → otp_verified → signed / rejected), unique signing token (UUID), OTP verification flag, signed timestamp, rejection reason, forensic metadata (IP, user agent, device info), reminder count.
- `CapturedSignature` — The actual signature image. Sources: drawn on canvas, typed text rendered as image, uploaded image. Stores image file, base64 data URI, typed text + font, is_default flag for reuse.
- `DocumentSigningEvent` — The final linking record connecting a `SignerAssignment` to its `CapturedSignature`, with event type (signed, rejected, viewed, otp_sent, otp_verified, reminder_sent, finalised), IP, user agent, and notes.
- `SigningOTP` — Short-lived OTP records for verifying signer identity via email.
- `AuditEntry` — Immutable per-document audit log entries (actor, action, timestamp, IP, extra JSON).

**Workflow:**
1. Uploader submits PDF via `DocumentUploadView` with signer count, names, emails, and order.
2. `SignableDocumentUploadSerializer.create()` saves the PDF, computes SHA-256, creates `SignerAssignment` rows, and advances status from `draft` → `pending`.
3. Celery task `send_signing_invitation` emails each signer a unique tokenized signing URL.
4. Signer clicks link → `SigningInterfaceView` validates token and shows the signing interface.
5. If OTP required: signer requests OTP → `send_otp_email` task fires → signer enters code → verified.
6. Signer draws/types/uploads signature → `CaptureSignatureView` saves `CapturedSignature` + `DocumentSigningEvent`, updates `SignerAssignment.status = signed`.
7. After all required signers have signed: Celery task `finalise_signed_document` embeds all captured signatures into the PDF using ReportLab, appends a manifest/audit page, computes final SHA-256, stores `signed_file`, and sets status `fully_signed`.
8. Uploader and all signers receive a completion notification with the final signed PDF.

**PDF Service (`pdf_service.py`):** Handles embedding signature images into the correct PDF page coordinates and appending a full cryptographic audit manifest as a final page.

---

### Voting

**Path:** `apps/voting/`

Board motions and electronic voting.

**Models:**
- `Motion` — Title, description, background, category (governance, financial, strategic, operational, compliance, personnel), voting type (simple majority, qualified majority, two-thirds, unanimous, consensus), status (draft → proposed → debate → voting → passed/failed/withdrawn/tabled), linked meeting, proposer, seconder, anonymous voting flag.
- `Vote` — Individual vote record (for, against, abstain) with voter and timestamp.
- `VotingRound` — Groups votes in a timed round with open/close timestamps.
- `MotionComment` — Comments/debate contributions on a motion.

**Celery task:** `auto_close_expired_resolutions` runs every 5 minutes to close voting rounds past their deadline and tally results.

---

### Risk Management

**Path:** `apps/risk/`

Enterprise risk register.

**Models:**
- `RiskCategory` — Hierarchical risk categories (Strategic, Operational, Financial, Compliance, Reputational, Cybersecurity, Market, Regulatory, Environmental).
- `Risk` — Individual risk entry with probability (1-5), impact (1-5), risk score = probability × impact, owner, status (identified, assessed, mitigated, accepted, transferred, closed), linked category, residual risk, treatment plan.
- `RiskReview` — Periodic review records with updated scores and reviewer notes.
- `RiskTreatment` — Treatment actions with assignee and due date.

---

### Policy

**Path:** `apps/policy/`

Full governance policy lifecycle.

**Models:**
- `PolicyCategory` — Hierarchical categories with `get_full_path()` for breadcrumbs.
- `Policy` — Document body, version, status (draft → review → approved → published → archived → superseded), review cycle, owner, approver, effective date, expiry date, related policies.
- `PolicyVersion` — Historical version snapshots for full audit history.
- `PolicyReview` — Review assignments with feedback and outcome.

---

### Evaluation

**Path:** `apps/evaluation/`

Board and director performance evaluation.

**Models:**
- `EvaluationTemplate` — Configurable questionnaire with evaluator instructions, evaluation type (board, director, committee, CEO), and linked questions.
- `EvaluationQuestion` — Question text, type (rating, text, yes/no), weight, category.
- `EvaluationCycle` — A named evaluation run assigned to evaluators with deadline and status.
- `EvaluationResponse` — Individual response records (scores + comments per question).
- `EvaluationResult` — Aggregated results per cycle.

**Template tags** (`apps/evaluation/templatetags/evaluation_tags.py`): Helper filters for rendering evaluation scores, progress bars, and result summaries in templates.

---

### Discussions

**Path:** `apps/discussions/`

Secure threaded discussion forums for board communications.

**Models:**
- `DiscussionForum` — Named forums with type (general, strategy, governance, finance, operations, risk, policy, confidential, committee, emergency) and access level (public, restricted, confidential, private).
- `DiscussionThread` — A topic thread within a forum, with pin, lock, and view-count.
- `DiscussionPost` — Threaded replies with rich content, mentions, attachments.
- `DiscussionParticipant` — Tracks who has been added to restricted/private forums.

---

### Notifications

**Path:** `apps/notifications/`

In-app notification engine.

**Models:**
- `Notification` — Typed notification (meeting_reminder, voting_open, document_shared, risk_alert, security_alert, etc.) with priority (low, normal, high, urgent), read status, target URL, and delivery timestamps.

**Types covered:** Meeting reminders & updates, voting open/close/results, document shared/updated, policy update, risk alert, evaluation assigned/reminder, discussion reply/mention, audit alert, system update, security alert.

**Template:** `templates/notifications/quick_notification.html` — HTMX-powered quick notification panel.

---

### Audit

**Path:** `apps/audit/`

Immutable, system-wide audit trail.

**Models:**
- `AuditLog` — Records actor, action performed, content type + object ID (via generic FK), before/after field values, IP address, user agent, timestamp. Append-only — no update/delete endpoints exist.

Celery task `run_database_backup` fires daily at 2 AM (Nairobi time) via Celery Beat.

---

### Analytics

**Path:** `apps/analytics/`

Governance engagement and participation analytics.

**Features:**
- Meeting attendance rates per branch / committee / period
- Voting participation and trend charts
- Document access and sharing statistics
- User engagement scoring

---

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 15+
- Redis 7+
- Node.js (optional — only if rebuilding Tailwind CSS from source)
- Git

---

### Installation

```
/dev/null/bash.sh#L1-20
# 1. Clone the repository
git clone https://github.com/Kemboi14/Ebooard2.git
cd Ebooard2

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # Linux / macOS
# venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements/development.txt

# 4. Copy the example environment file and fill in your values
cp .env.example .env
```

---

### Environment Variables

Create a `.env` file in the project root (never commit this file). All variables are read via `python-decouple`.

```
/dev/null/.env.example#L1-30
# ── Django Core ──────────────────────────────────────────────────
SECRET_KEY=your-very-long-random-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# ── Database ─────────────────────────────────────────────────────
DB_NAME=enwealth_eboard
DB_USER=enwealth_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432

# ── Redis / Celery ───────────────────────────────────────────────
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# ── Email ────────────────────────────────────────────────────────
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=Enwealth Board Portal <noreply@enwealth.com>

# ── Site URL (used in email links) ───────────────────────────────
SITE_URL=http://localhost:8000

# ── Session ──────────────────────────────────────────────────────
SESSION_COOKIE_AGE=3600
```

---

### Database Setup

```
/dev/null/bash.sh#L1-12
# Create the PostgreSQL database and user
psql -U postgres -c "CREATE USER enwealth_user WITH PASSWORD 'your_db_password';"
psql -U postgres -c "CREATE DATABASE enwealth_eboard OWNER enwealth_user;"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE enwealth_eboard TO enwealth_user;"

# Run migrations
python manage.py migrate

# Create a superuser (admin account)
python manage.py createsuperuser

# (Optional) Load initial fixture data
python manage.py loaddata fixtures/initial_data.json
```

---

### Running the Development Server

```
/dev/null/bash.sh#L1-5
# Make sure your virtual environment is active and .env is populated
export DJANGO_SETTINGS_MODULE=config.settings.development

python manage.py runserver
# → http://127.0.0.1:8000
```

---

### Running Celery Workers

Open two additional terminals (with venv activated):

```
/dev/null/bash.sh#L1-8
# Terminal 1 — Celery worker (processes async tasks)
celery -A config.celery worker --loglevel=info

# Terminal 2 — Celery Beat (periodic / scheduled tasks)
celery -A config.celery beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

**Scheduled tasks (via Celery Beat):**

| Task | Schedule |
|---|---|
| `apps.voting.tasks.auto_close_expired_resolutions` | Every 5 minutes |
| `apps.meetings.tasks.send_upcoming_meeting_reminders` | Daily at 08:00 EAT |
| `apps.audit.tasks.run_database_backup` | Daily at 02:00 EAT |

---

## User Roles & Permissions

| Role | Description | Key Permissions |
|---|---|---|
| `board_member` | Director / Board Member | View meetings, vote, sign documents, access discussions |
| `company_secretary` | Board Secretary | Full meeting management, document upload, e-signature, notifications |
| `executive_management` | C-Suite / Executive | Full read access, voting, risk management |
| `compliance_officer` | Compliance & Risk Officer | Risk register, policy management, audit trail |
| `it_administrator` | IT / System Admin | User management, system settings, audit trail |
| `internal_audit` | Internal Auditor | Read-only access to all modules + audit trail |

**MFA Required Roles:** `it_administrator`, `company_secretary`, `executive_management`, `compliance_officer`, `board_member` — these roles must complete TOTP setup within 7 days of account creation.

Permissions are enforced at three levels:
1. **Global role** — `user.role` on the `User` model
2. **Branch role** — `UserBranchMembership.branch_role` (can differ from global role)
3. **Committee role** — `CommitteeMembership.committee_role`

---

## Multi-Timezone Support

The platform operates across multiple time zones:

| Region | Timezone | Offset |
|---|---|---|
| Kenya, Uganda, Tanzania | `Africa/Nairobi` | UTC+3 (EAT) |
| Mauritius | `Indian/Mauritius` | UTC+4 (MUT) |
| South Africa | `Africa/Johannesburg` | UTC+2 (SAST) |
| Nigeria | `Africa/Lagos` | UTC+1 (WAT) |
| United Kingdom | `Europe/London` | UTC+0 / UTC+1 (BST) |
| UAE | `Asia/Dubai` | UTC+4 (GST) |

**Implementation:**
- All datetimes are stored as UTC-aware in PostgreSQL (`USE_TZ = True`).
- The project default timezone is `Africa/Nairobi` (`TIME_ZONE` setting).
- Each `User` has a `preferred_timezone` field (IANA timezone string).
- Template tag library `apps/accounts/templatetags/tz_tags.py` provides:
  - `{{ dt|localtime:request.user }}` — Converts a datetime to the user's local time
  - `{% tz_abbr request.user %}` — Renders timezone abbreviation (e.g. EAT, MUT)
  - `{% meeting_time meeting request.user %}` — Renders a formatted meeting time in user's tz
  - `{% timezone_notice meeting request.user %}` — Shows a notice banner when the user's tz differs from the branch's tz

---

## E-Signature Workflow

```
/dev/null/esign-flow.txt#L1-18
Uploader
  │
  ├─► POST /esignature/upload/
  │       └─ SavePDF → SHA-256 hash → Create SignerAssignment rows
  │           └─ Status: draft → pending
  │
  ├─► Celery: send_signing_invitation → Email tokenized link to each signer
  │
Signer (internal user or external by email)
  │
  ├─► GET /esignature/sign/<token>/
  │       └─ Validate token → Show signing interface
  │
  ├─► POST /esignature/sign/<token>/otp/request/   (if OTP required)
  │       └─ Generate OTP → Celery: send_otp_email
  │
  ├─► POST /esignature/sign/<token>/otp/verify/
  │       └─ Verify OTP → Mark SignerAssignment.otp_verified = True
  │
  ├─► POST /esignature/sign/<token>/capture/
  │       └─ Save CapturedSignature (drawn/typed/uploaded)
  │           └─ Create DocumentSigningEvent
  │               └─ Update SignerAssignment.status = signed
  │                   └─ If all signed → Celery: finalise_signed_document
  │
Celery: finalise_signed_document
  │
  └─► Embed all signatures into PDF (ReportLab)
      └─ Append audit manifest page
          └─ Compute signed SHA-256
              └─ Store signed_file, set status = fully_signed
                  └─ Notify uploader + all signers
```

**Security features:**
- Each signer gets a unique UUID token that expires.
- OTP is short-lived (configurable via `ESIGNATURE_OTP_EXPIRY_MINUTES`, default 10 minutes).
- Forensic metadata (IP, user agent, device info) is captured at signing time.
- Both original and signed file SHA-256 hashes are stored for tamper detection.
- An immutable `AuditEntry` is written for every step.
- Max file size enforced (`ESIGNATURE_MAX_FILE_SIZE_MB`, default 20 MB).
- Only PDF MIME type accepted (`ESIGNATURE_ALLOWED_MIME_TYPES`).

---

## Security

- **CSRF:** Enforced on all state-changing requests. Development uses a separate cookie name (`csrftoken_dev`) to avoid stale-cookie issues. Logout is CSRF-exempt and accepts GET (safe to do for logout actions).
- **Session:** `SESSION_EXPIRE_AT_BROWSER_CLOSE = True`. Configurable `SESSION_COOKIE_AGE` (default 1 hour).
- **HTTPS in production:** Set `CSRF_COOKIE_SECURE = True`, `SESSION_COOKIE_SECURE = True`, and configure your reverse proxy (Nginx/Caddy) to terminate TLS.
- **MFA:** TOTP mandatory for privileged roles. Grace period enforced.
- **Password history:** Prevents reuse of recent passwords (`PasswordHistory` model).
- **Rate limiting:** `django-ratelimit` applied to login and OTP endpoints.
- **File validation:** `python-magic` validates MIME types on upload (not just file extension).
- **Secrets:** All secrets read from `.env` via `python-decouple`. Never hard-coded.
- **Audit trail:** All critical actions are logged immutably in `AuditLog`.
- **Permissions:** Every view is protected by role-based decorators/mixins. Anonymous users are redirected to login.
- **XSS / Clickjacking:** Django's `XFrameOptionsMiddleware` and template auto-escaping active by default.

---

## API

The platform exposes a Django REST Framework API for programmatic access and HTMX partial rendering.

**Base URL:** `/api/` (extend in `config/urls.py` as needed)

**Authentication:** Session authentication (cookie-based) and HTTP Basic Authentication.

**Throttling:**
- Anonymous: 20 requests/hour
- Authenticated: 200 requests/hour

**Pagination:** Page-number pagination, 25 results per page.

**Key serializers:**
- `SignableDocumentUploadSerializer` — Accepts flat signer fields from upload form, maps to nested `initial_signers`, creates assignments, and transitions document status.

DRF browsable API is available in development at `/api/`.

---

## Deployment

### Production Checklist

```
/dev/null/bash.sh#L1-20
# 1. Set production environment variables in .env
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
SITE_URL=https://yourdomain.com

# 2. Install production dependencies
pip install -r requirements/production.txt

# 3. Collect static files
python manage.py collectstatic --noinput

# 4. Run migrations
python manage.py migrate

# 5. Start Gunicorn
gunicorn config.wsgi:application \
  --workers 4 \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile logs/access.log \
  --error-logfile logs/error.log

# 6. Start Celery (use supervisord or systemd in production)
celery -A config.celery worker --loglevel=warning --concurrency=4
celery -A config.celery beat --loglevel=warning
```

### Nginx Configuration (example)

```
/dev/null/nginx.conf#L1-25
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate     /etc/ssl/certs/yourdomain.crt;
    ssl_certificate_key /etc/ssl/private/yourdomain.key;

    location /static/ {
        alias /path/to/Ebooard2/staticfiles/;
        expires 30d;
    }

    location /media/ {
        alias /path/to/Ebooard2/media/;
        internal;  # Serve via X-Accel-Redirect for protected files
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Production Security Settings

Ensure these are set in `config/settings/production.py`:

```
/dev/null/production_settings.py#L1-10
DEBUG = False
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
X_FRAME_OPTIONS = "DENY"
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
```

### File Storage

For production, consider replacing the local `MEDIA_ROOT` with Amazon S3 or compatible object storage using `django-storages`:

```
/dev/null/s3_settings.py#L1-8
DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
AWS_STORAGE_BUCKET_NAME = "your-bucket-name"
AWS_S3_REGION_NAME = "af-south-1"
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = "private"
AWS_S3_CUSTOM_DOMAIN = None
MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/"
```

---

## Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes with tests where applicable.
4. Run the test suite: `python manage.py test`
5. Commit with a descriptive message following [Conventional Commits](https://www.conventionalcommits.org/).
6. Open a Pull Request against the `main` branch.

**Code style:** PEP 8. Use `black` for formatting and `flake8` for linting.

---

## License

This project is proprietary software owned by **Enwealth**. All rights reserved.  
Unauthorized copying, modification, distribution, or use of this software is strictly prohibited.

---

<p align="center">Built with ❤️ for better board governance across Africa and beyond.</p>