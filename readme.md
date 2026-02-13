# ComplianceOS — README (User Guide + Feature Overview)

ComplianceOS is a **compliance task management system** for a firm. It helps you:
- Track tasks per client with due dates and recurring series
- Automatically send **start emails** and **completion emails** to clients
- Coordinate internal teams (Partner / Manager / Associate)
- Maintain a full activity trail (status changes, edits, attachments, comments)
- Export reports to **Excel (XLSX)** and **PDF**
- Do **offline bulk edits** in Excel and re-upload to update tasks safely

This README is written for someone who has never seen the app before.

---

## 1) Who is this for?

A professional services firm (tax/compliance/accounting/audit) that manages many client deadlines and needs:
- Clear ownership (who is responsible)
- Automated client communication
- Auditability (who changed what and when)
- Reporting and exports for partners/management
- A safe workflow for bulk edits through Excel

---

## 2) Key concepts (plain English)

### Client
A client profile contains:
- Client name and identifiers (PAN/GSTIN/CIN/AY etc.)
- Default email recipients (Primary + CC/BCC lists)

Tasks can use these defaults, or override recipients per task.

### Task
A task is a single piece of work like “GSTR-3B Filing” with:
- Start date (computed from due date + trigger days)
- Due date
- Assigned person
- Status + notes
- Email templates (start + completion) and recipient settings
- Attachments (uploaded to Google Drive)
- Comments (internal discussion)
- Timeline/audit log (history of changes)

### Series (recurring tasks)
A series is a repeating task pattern (monthly/quarterly/etc.). The system creates multiple tasks with different due/start dates.

### Roles
- **PARTNER**: Full control. Creates/edits clients, edits all tasks, exports, admin tools.
- **MANAGER**: Similar to partner for tasks/exports (but client admin can be restricted).
- **ASSOCIATE**: Works on assigned tasks (updates status, adds comments, uploads attachments). Cannot mark tasks COMPLETED (partner/manager does final completion).

> Backward compatibility: if any user is stored as `WORKER` in old data, it is treated as **ASSOCIATE**.

---

## 3) Login & accounts

### Sign in
- Use your firm email + password.
- If your password doesn’t work, use **Forgot password** to receive a reset email.

### Create account
- Creates your account and a default user record.
- A partner should set your correct role later (Partner/Manager/Associate).

---

## 4) Main navigation (what each area does)

The UI has 6 main areas (left rail):

### 1) Overview
A snapshot:
- Overdue counts
- Due today / next 7 days
- Approval pending
- Snoozed items
- “Focus list” of urgent tasks

### 2) Work Queue
Your main working screen:
- Search and filters (status, category, priority, assignee, due range)
- Select tasks and run **bulk actions**
- Open a task in the **Task Inspector** to work on it

### 3) Timeline
A calendar-style view:
- Month heatmap based on number of tasks due each day
- Tap a day to see the day agenda
- Agenda view for chronological scanning

### 4) Clients (Partner-only)
- Create new clients
- Edit client master data (emails/identifiers)
- Download client history exports (XLSX/PDF)

### 5) Studio
Email drafting tool:
- Insert dynamic fields like `{{clientName}}`, `{{taskTitle}}`
- Excel-safe copying (keeps multiple lines inside one Excel cell)
- Copy subject/body quickly

### 6) Ops & Reports (Partner/Manager)
Operations + reports:
- Import tasks from Excel
- Export reports to XLSX and PDFs
- Offline update workflow (export → edit → upload update XLSX)
- Partner admin: team management, settings, migrations

---

## 5) Task lifecycle (how work normally flows)

### Step A — Task is created
Tasks can be created:
- Individually from the UI (Task Inspector → Create mode)
- As a series (monthly/quarterly) in the same flow
- Via Excel import (Ops → Import)

### Step B — Start email is sent (optional)
A start email can be sent:
- Immediately if the task’s start date is today
- Otherwise on the start date automatically (scheduled run)

Start email can be disabled per task:
- If start mail is disabled, the system will not email the client’s “To”
- Internal recipients can still receive it (To is promoted from CC/BCC if needed)

### Step C — Associate works on the task
Associate typically:
- Updates status: PENDING → IN_PROGRESS → CLIENT_PENDING → APPROVAL_PENDING
- Adds notes and delay reasons if needed
- Uploads attachments (returns, challans, acknowledgements)
- Comments internally and @mentions colleagues

### Step D — Partner/Manager completes task
When Partner/Manager sets status to **COMPLETED**:
- Calendar event is updated/marked completed
- Completion email is sent (if enabled)

**Completion email behavior:**  
It replies in the **same Gmail thread** as the start email (reply-all behavior) when thread metadata exists.

---

## 6) Task statuses (meaning)

Typical statuses:
- **PENDING**: Not started yet
- **IN_PROGRESS**: Work started internally
- **CLIENT_PENDING**: Waiting on client input/documents
- **APPROVAL_PENDING**: Work done; waiting for approval to complete
- **COMPLETED**: Final done (Partner/Manager only)

---

## 7) Emails (start + completion) — how they work

### Templates
Each task can store:
- Start email subject and body
- Completion email subject and body

Supported template fields:
- `{{clientName}}`
- `{{taskTitle}}`
- `{{startDate}}`
- `{{dueDate}}`
- `{{addToCalendarUrl}}`
- `{{completedAt}}`

### Recipients (default vs override)
Recipients can come from:
1) Client master profile (primary email + default CC/BCC)
2) Per-task overrides (To/CC/BCC arrays)

### Start mail send toggle
A per-task boolean:
- If disabled: the app removes the client “To” recipients  
- It can still send internal trail recipients (CC/BCC)  
- If Gmail requires a “To” and “To” is empty, the system promotes first CC/BCC into To

### Completion mail (reply-all)
Completion mail:
- Replies to the start email thread if the start thread exists
- Uses completion override recipients if configured
- Can CC assignee and/or manager based on task flags

---

## 8) Comments and @mentions

Each task has a comment thread.
- Type `@email@firm.com` or `@Display Name` to mention someone
- Mentions create a notification record for the mentioned user (backend feature)

Comments are stored under the task and can be exported in task history exports.

---

## 9) Attachments (Google Drive)

You can upload files to a task:
- The system uploads to Google Drive under a client folder
- Task stores file metadata + Drive link
- Attachments are visible in the task inspector and included in exports as links

---

## 10) Bulk actions (Work Queue)

Select multiple tasks and run:
- Bulk status change
- Bulk reassign (Partner/Manager)
- Bulk snooze
- Bulk delete (permission-checked)

Permissions are enforced server-side.

---

## 11) Exports & reports (Excel + PDF)

### Excel (XLSX) exports
- **Firm range with history**: includes tasks + mail fields + audit logs
- **Quick exports**: next 7/15/30 days, overdue, approval pending
- **Client history XLSX**: all tasks for a client with full fields
- **Task history XLSX**: full history for one task:
  - Task fields
  - Audit log
  - Comments
  - Attachments links

### PDF reports (server-generated)
- Firm range PDF
- Client history PDF
- Task history PDF
- Daily digest PDF
- Monthly summary PDF

> These PDFs are generated on the server (not browser “print”).

---

## 12) Offline workflow: Excel bulk edit → upload to update tasks

This is one of the strongest features.

### How it works
1) Go to **Ops & Reports → Offline updates**
2) Download:
   - **Update Template XLSX** (blank format)
   - or **Export tasks for update XLSX** (pre-filled with current task data)
3) Edit rows offline in Excel:
   - status, notes, snooze, assignee, due date (privileged only), recipient overrides, mail flags, etc.
4) Upload the edited XLSX
5) System updates tasks and writes audit logs

### Safety rules
- XLSX must include `TaskId` to update the correct task.
- Associates can only update their own tasks and cannot set COMPLETED.
- Partner/Manager can update all tasks and sensitive fields.

---

## 13) Calendar integration

Each task creates a calendar event on the **start date**.
- When task dates change (privileged), calendar events are patched.
- When task is completed, calendar events are updated with completed prefix/color.

---

## 14) Security & permissions

- All writes go through backend endpoints secured by Firebase ID token.
- Role checks are enforced on backend:
  - Partner-only: clients, admin settings, team management
  - Manager/Partner: edit task details, complete tasks, exports
  - Associate: update status (not COMPLETED), comment, upload attachments, delete only own task (not entire series)

---

## 15) Accessibility & usability notes

The UI supports:
- Keyboard-first navigation (Command palette)
- ESC to close modals/inspector
- Clear labels and consistent spacing
- High-contrast visual states
- Responsive layout (mobile rail becomes bottom nav)

---

## 16) Common workflows (quick recipes)

### A) Create tasks for a new client (Partner)
1. Clients → Create client
2. Task Inspector → Create task (or import template)
3. Verify start mail / completion mail settings
4. Assign to associate

### B) Associate working daily
1. Work Queue → Mode: Active
2. Filter Due soon / Overdue using search + due range
3. Open task → update status + add note
4. Upload file → add comment mentioning manager if needed

### C) Partner completing work
1. Work Queue → Mode: Approval pending
2. Open task → review notes/attachments
3. Set status COMPLETED (sends completion email as reply-all when possible)

### D) Offline monthly clean-up
1. Ops → Export tasks for update XLSX
2. Bulk edit assignees/due dates/notes offline
3. Upload updates XLSX
4. Download firm range PDF for reporting

---

## 17) Troubleshooting

### “Forgot password email not received”
This typically depends on Firebase Auth configuration:
- Authorized domains must include your domain
- Email/Password sign-in must be enabled
- Check spam/junk folders

### “Completion email didn’t thread”
Threading requires start email thread metadata. If start email wasn’t sent or thread IDs were missing, completion email falls back to a new message.

### “Import says password required”
Partner can enable Associate import password in Ops → Admin.

---

## 18) Feature list (complete)

### Core
- Client management (create/update)
- Task create (single and series)
- Start mail: immediate + scheduled + send control
- Completion mail: reply-all thread + overrides + internal trail
- Comments + @mentions notifications
- Attachments upload to Drive
- Full audit log timeline

### Bulk operations
- Bulk status, reassign, snooze, delete (permission enforced)

### Exports / Reports
- XLSX: firm range w/history, quick exports, client history, task history
- PDF: firm range, client history, task history, daily digest, monthly summary

### Offline operations
- Update template XLSX
- Export-for-update XLSX
- Upload XLSX to update existing tasks (with audit logs)

### Admin (Partner)
- Team list + role changes
- Manager mapping
- Display names
- Digest settings + calendar settings
- Associate import password
- Role migration (WORKER → ASSOCIATE)

---

## 19) Getting started (recommended first steps)

1. Partner signs in and confirms role is PARTNER
2. Add clients (Clients section)
3. Create a few tasks (Create task in inspector or XLSX import)
4. Set up team roles and manager mapping (Ops → Admin)
5. Run exports for verification (Ops → Exports)
6. Try the offline update workflow with a small sample

