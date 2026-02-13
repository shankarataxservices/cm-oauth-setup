#!/usr/bin/env python3
"""
================================================================
TASK MANAGEMENT APP — PENDING CHANGES PATCHER
================================================================
Applies all UI + Backend pending changes with:
  - Fuzzy whitespace matching (handles indentation differences)
  - .bak backup of every file before modification
  - Deep verbose logging of every step
  - Dry-run option
================================================================
"""

import os
import re
import sys
import shutil
import tkinter as tk
from tkinter import filedialog
from datetime import datetime
from copy import deepcopy

# ──────────────────────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────────────────────

class Logger:
    def __init__(self):
        self.logs = []
        self.indent = 0
        self.counts = {"success": 0, "skip": 0, "fail": 0, "warn": 0}

    def _emit(self, tag, msg):
        prefix = "  " * self.indent
        line = f"[{tag}] {prefix}{msg}"
        self.logs.append(line)
        print(line)

    def info(self, msg):    self._emit("INFO ", msg)
    def ok(self, msg):      self._emit(" OK  ", msg); self.counts["success"] += 1
    def warn(self, msg):    self._emit("WARN ", msg); self.counts["warn"] += 1
    def fail(self, msg):    self._emit("FAIL ", msg); self.counts["fail"] += 1
    def skip(self, msg):    self._emit("SKIP ", msg); self.counts["skip"] += 1
    def step(self, msg):    self._emit("STEP ", msg)
    def detail(self, msg):  self._emit("    >", msg)
    def blank(self):        print(""); self.logs.append("")

    def section(self, title):
        sep = "═" * 60
        self.blank()
        self._emit("═══", sep)
        self._emit("═══", f"  {title}")
        self._emit("═══", sep)

    def summary(self):
        self.blank()
        self.section("FINAL SUMMARY")
        self.info(f"Successful replacements : {self.counts['success']}")
        self.info(f"Skipped (already done?) : {self.counts['skip']}")
        self.info(f"Warnings                : {self.counts['warn']}")
        self.info(f"Failures                : {self.counts['fail']}")
        if self.counts["fail"] > 0:
            self.fail("SOME PATCHES FAILED — review log above!")
        else:
            self.ok("ALL PATCHES APPLIED SUCCESSFULLY")

log = Logger()

# ──────────────────────────────────────────────────────────────
# FUZZY MATCHING ENGINE
# ──────────────────────────────────────────────────────────────

def normalize_whitespace(text):
    """Collapse each line's leading whitespace to single spaces, strip trailing."""
    lines = text.split('\n')
    result = []
    for line in lines:
        stripped = line.rstrip()
        if not stripped:
            result.append('')
            continue
        leading = len(line) - len(line.lstrip())
        # Normalize leading whitespace: convert tabs to spaces, then collapse
        lead_str = line[:leading].replace('\t', '    ')
        # Keep relative indentation but normalize
        result.append(lead_str + line.lstrip())
    return '\n'.join(result)


def make_fuzzy_pattern(search_text):
    """
    Build a regex that matches the search_text with flexible whitespace.
    Each line's leading whitespace becomes \\s* and internal whitespace becomes \\s+.
    """
    lines = search_text.strip().split('\n')
    line_patterns = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            line_patterns.append(r'\s*')
            continue
        # Escape special regex chars
        escaped = re.escape(stripped)
        # Allow flexible internal whitespace (where original had spaces)
        escaped = escaped.replace(r'\ ', r'\s+')
        # Allow any leading whitespace
        line_patterns.append(r'[ \t]*' + escaped)
    # Join with flexible newline matching
    pattern = r'\n'.join(line_patterns)
    return pattern


def fuzzy_find(content, search_text):
    """
    Try to find search_text in content with fuzzy whitespace matching.
    Returns (start, end) of match or None.
    """
    # Strategy 1: Exact match (fastest)
    idx = content.find(search_text.strip())
    if idx != -1:
        end = idx + len(search_text.strip())
        return (idx, end, "exact")

    # Strategy 2: Stripped-line match
    search_lines = [l.strip() for l in search_text.strip().split('\n') if l.strip()]
    content_lines = content.split('\n')

    if not search_lines:
        return None

    for i in range(len(content_lines)):
        if content_lines[i].strip() == search_lines[0]:
            # Try to match all subsequent lines
            matched = True
            j = i
            matches = []
            si = 0
            while si < len(search_lines) and j < len(content_lines):
                if content_lines[j].strip() == '':
                    j += 1
                    continue
                if content_lines[j].strip() == search_lines[si]:
                    matches.append(j)
                    si += 1
                    j += 1
                else:
                    matched = False
                    break
            if matched and si == len(search_lines):
                # Calculate character positions
                start_pos = sum(len(content_lines[k]) + 1 for k in range(matches[0]))
                end_line = matches[-1]
                end_pos = sum(len(content_lines[k]) + 1 for k in range(end_line + 1))
                # Don't include the final newline if the content doesn't end with one
                if end_pos > 0 and end_pos <= len(content):
                    return (start_pos, end_pos - 1, "line-stripped")

    # Strategy 3: Regex fuzzy
    try:
        pattern = make_fuzzy_pattern(search_text)
        m = re.search(pattern, content)
        if m:
            return (m.start(), m.end(), "regex-fuzzy")
    except re.error:
        pass

    return None


def detect_indentation(content, position):
    """Detect the indentation used at a specific position in content."""
    # Find the start of the line
    line_start = content.rfind('\n', 0, position)
    if line_start == -1:
        line_start = 0
    else:
        line_start += 1
    line_text = content[line_start:position + 50]
    leading = len(line_text) - len(line_text.lstrip())
    return line_text[:leading]


def reindent_replacement(replacement_text, original_indent):
    """Re-indent replacement text to match the original code's indentation."""
    lines = replacement_text.split('\n')
    if not lines:
        return replacement_text

    # Find the minimum indentation in replacement (ignoring blank lines)
    min_indent = float('inf')
    for line in lines:
        if line.strip():
            leading = len(line) - len(line.lstrip())
            min_indent = min(min_indent, leading)
    if min_indent == float('inf'):
        min_indent = 0

    # Re-indent
    result = []
    for line in lines:
        if line.strip():
            result.append(original_indent + line[min_indent:])
        else:
            result.append('')
    return '\n'.join(result)

# ──────────────────────────────────────────────────────────────
# FILE OPERATIONS
# ──────────────────────────────────────────────────────────────

def read_file(path):
    log.detail(f"Reading: {path}")
    if not os.path.isfile(path):
        log.fail(f"File NOT FOUND: {path}")
        return None
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    log.detail(f"Read {len(content)} chars, {content.count(chr(10))} lines")
    return content


def write_file(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    log.detail(f"Written {len(content)} chars to {path}")


def backup_file(path):
    if not os.path.isfile(path):
        return False
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak_path = f"{path}.{ts}.bak"
    shutil.copy2(path, bak_path)
    log.detail(f"Backup created: {bak_path}")
    return True

# ──────────────────────────────────────────────────────────────
# PATCH APPLICATION ENGINE
# ──────────────────────────────────────────────────────────────

def apply_patch(content, patch_id, search_text, replace_text, mode="replace"):
    """
    Apply a single patch.
    mode: "replace" — find search_text and replace with replace_text
          "insert_after" — find search_text, keep it, insert replace_text after
          "insert_before" — find search_text, insert replace_text before it, keep search_text
          "remove_and_replace" — same as replace
    Returns (new_content, success)
    """
    log.step(f"Applying patch: {patch_id}")
    log.indent += 1

    # Check if replacement text already exists (patch already applied)
    replace_check = replace_text.strip()
    # Use first meaningful line of replacement as check
    replace_lines = [l.strip() for l in replace_check.split('\n') if l.strip()]
    if replace_lines:
        # Check if a distinctive line from replacement already exists
        # Use a line that's NOT in the search text
        search_lines_set = set(l.strip() for l in search_text.strip().split('\n'))
        unique_replace_lines = [l for l in replace_lines if l not in search_lines_set]

        if unique_replace_lines:
            check_line = unique_replace_lines[0]
            if check_line in content:
                log.skip(f"Patch {patch_id} appears ALREADY APPLIED (found: '{check_line[:80]}...')")
                log.indent -= 1
                return content, True

    # Find the search text
    result = fuzzy_find(content, search_text)

    if result is None:
        log.fail(f"Could not find search text for patch {patch_id}")
        log.detail(f"Search text (first 120 chars): {search_text.strip()[:120]}")
        log.indent -= 1
        return content, False

    start, end, method = result
    log.detail(f"Found match using method: {method} at chars {start}-{end}")
    matched_text = content[start:end]
    log.detail(f"Matched text preview: {matched_text[:100]}...")

    # Detect indentation of the matched block
    orig_indent = detect_indentation(content, start)
    log.detail(f"Detected indentation: {repr(orig_indent)}")

    if mode == "replace":
        new_content = content[:start] + replace_text.strip() + content[end:]
        log.ok(f"Patch {patch_id} applied successfully (replace)")
    elif mode == "insert_after":
        new_content = content[:end] + '\n' + replace_text.strip() + content[end:]
        log.ok(f"Patch {patch_id} applied successfully (insert_after)")
    elif mode == "insert_before":
        new_content = content[:start] + replace_text.strip() + '\n' + content[start:]
        log.ok(f"Patch {patch_id} applied successfully (insert_before)")
    else:
        new_content = content[:start] + replace_text.strip() + content[end:]
        log.ok(f"Patch {patch_id} applied successfully")

    log.indent -= 1
    return new_content, True

# ──────────────────────────────────────────────────────────────
# PATCH DEFINITIONS
# ──────────────────────────────────────────────────────────────

def get_ui_patches():
    """All UI patches for index.html"""
    patches = []

    # ── UI-1: Bulk status dropdown — always include COMPLETED ──
    patches.append({
        "id": "UI-1: Bulk status dropdown include COMPLETED",
        "search": """function allowedStatusesForBulk() {
 const base = ['PENDING', 'IN_PROGRESS', 'CLIENT_PENDING', 'APPROVAL_PENDING'];
 if (state.isPartner || state.isManager) base.push('COMPLETED');
 return base;
}""",
        "replace": """function allowedStatusesForBulk() {
 // Everyone can set COMPLETED for tasks they are allowed to edit (backend enforces ownership)
 return ['PENDING', 'IN_PROGRESS', 'CLIENT_PENDING', 'APPROVAL_PENDING', 'COMPLETED'];
}""",
        "mode": "replace"
    })

    # ── UI-2: Help text update ──
    patches.append({
        "id": "UI-2: Help text role statement update",
        "search": """<b>ASSOCIATE</b>: update statuses, add comments, upload attachments.<br>
<b>MANAGER / PARTNER</b>: edit task details, reassign, complete tasks, exports/reports.""",
        "replace": """<b>ASSOCIATE</b>: update statuses (including <b>COMPLETED</b> for tasks assigned to you), add comments, upload attachments.<br>
<b>MANAGER / PARTNER</b>: edit task details, reassign, exports/reports.""",
        "mode": "replace"
    })

    # ── UI-3: Task Drawer status dropdown — COMPLETED for all ──
    patches.append({
        "id": "UI-3: Task Drawer status dropdown COMPLETED for all",
        "search": """function statusOptionsForRole() {
 const base = ['PENDING', 'IN_PROGRESS', 'CLIENT_PENDING', 'APPROVAL_PENDING'];
 if (roleCanEditDetails()) base.push('COMPLETED');
 return base;
}""",
        "replace": """function statusOptionsForRole() {
 // Everyone can mark COMPLETED (backend enforces "must be assignee" for associates)
 return ['PENDING', 'IN_PROGRESS', 'CLIENT_PENDING', 'APPROVAL_PENDING', 'COMPLETED'];
}""",
        "mode": "replace"
    })

    # ── UI-4: Drawer dropdown width/overflow CSS fix ──
    patches.append({
        "id": "UI-4: Drawer dropdown width/overflow CSS fix",
        "search": """.cosTwoCol{ display:grid; grid-template-columns: repeat(12, 1fr); gap: 14px; }""",
        "replace": """.cosTwoCol{ display:grid; grid-template-columns: repeat(12, 1fr); gap: 14px; }

/* Dropdown width/overflow fix (prevents long client/type/status from stretching UI) */
.cosDrawerBody .field{ align-items:flex-start; }
.cosDrawerBody select.select{
 width: min(520px, 100%);
 max-width: 100%;
 white-space: nowrap;
 overflow: hidden;
 text-overflow: ellipsis;
}""",
        "mode": "replace"
    })

    # ── UI-5A: Expose openers ──
    patches.append({
        "id": "UI-5A: Expose __cos_openCreateOneTask",
        "search": """/* ---------- Expose openers to other parts ---------- */
window.__cos_openTaskInspector = (taskId) => renderTaskDrawer(taskId);
window.__cos_openCreateTask = () => renderCreateDrawer();""",
        "replace": """/* ---------- Expose openers to other parts ---------- */
window.__cos_openTaskInspector = (taskId) => renderTaskDrawer(taskId);
window.__cos_openCreateTask = () => renderCreateDrawer({ oneOnly: false });
window.__cos_openCreateOneTask = () => renderCreateDrawer({ oneOnly: true });""",
        "mode": "replace"
    })

    # ── UI-5B: renderCreateDrawer() support oneOnly ──
    patches.append({
        "id": "UI-5B: renderCreateDrawer support oneOnly",
        "search": """function renderCreateDrawer() {
 clearLive();
 drawerMode = 'create';
 currentTaskId = null;
 dTitle.textContent = 'Create task';
 dSub.textContent = 'Create one task or a repeating series (old UI form, new backend).';
 body.innerHTML = '';
 body.appendChild(card('Create task', 'Fill details, set emails, then create.', pill(state.role, ''), mountCreatePanel()));
 openDrawer();
}""",
        "replace": """function renderCreateDrawer({ oneOnly = false } = {}) {
 clearLive();
 drawerMode = 'create';
 currentTaskId = null;

 dTitle.textContent = oneOnly ? 'Create ONE task' : 'Create task';
 dSub.textContent = oneOnly
   ? 'Quick create: exactly one task (associates supported).'
   : 'Create one task or a repeating series (old UI form, new backend).';

 body.innerHTML = '';
 body.appendChild(
   card(
     oneOnly ? 'Create ONE task' : 'Create task',
     oneOnly ? 'One-time task only.' : 'Fill details, set emails, then create.',
     pill(state.role, ''),
     mountCreatePanel({ oneOnly })
   )
 );
 openDrawer();
}""",
        "mode": "replace"
    })

    # ── UI-5C: mountCreatePanel accept oneOnly ──
    patches.append({
        "id": "UI-5C: mountCreatePanel accept oneOnly",
        "search": """function mountCreatePanel() {""",
        "replace": """function mountCreatePanel({ oneOnly = false } = {}) {""",
        "mode": "replace"
    })

    # ── UI-5D: Force recurrence/count to ONE when oneOnly ──
    patches.append({
        "id": "UI-5D: Force recurrence/count when oneOnly",
        "search": """const genCount = h('input', { class: 'input', type: 'number', min: '1', value: '1' });""",
        "replace": """const genCount = h('input', { class: 'input', type: 'number', min: '1', value: '1' });

if (oneOnly) {
  recurrence.value = 'AD_HOC';
  recurrence.disabled = true;
  genCount.value = '1';
  genCount.disabled = true;
}""",
        "mode": "replace"
    })

    # ── UI-5E: Force payload recurrence/generateCount for oneOnly ──
    patches.append({
        "id": "UI-5E: Force payload for oneOnly",
        "search": """recurrence: recurrence.value,
generateCount: Number(genCount.value || 1),""",
        "replace": """recurrence: oneOnly ? 'AD_HOC' : recurrence.value,
generateCount: oneOnly ? 1 : Number(genCount.value || 1),""",
        "mode": "replace"
    })

    return patches


def get_backend_patches():
    """All backend patches, keyed by relative file path."""
    patches = {}

    # ── BE-1: tasks_updatestatus.js — Calendar completion patch shows Client NAME ──
    patches["netlify/functions/tasks_updatestatus.js"] = [
        {
            "id": "BE-1: Calendar completion patch Client NAME",
            "search": """const desc =
 `ClientId: ${task.clientId}\\n` +
 `Start: ${task.startDateYmd}\\n` +
 `Due: ${task.dueDateYmd}\\n`;""",
            "replace": """const cn = String(task.clientNameSnapshot || '').trim() || String(task.clientId || '').trim();
const extra = String(task.calendarDescription || '').trim();
const descBase =
 `Client: ${cn}\\n` +
 `Start: ${task.startDateYmd}\\n` +
 `Due: ${task.dueDateYmd}\\n`;
const desc = extra ? `${descBase}\\n${extra}` : descBase;""",
            "mode": "replace"
        }
    ]

    # ── BE-2: series_rebuild.js ──
    patches["netlify/functions/series_rebuild.js"] = [
        # BE-2A: Update imports
        {
            "id": "BE-2A: series_rebuild imports update",
            "search": """const {
 withCors, json, db, admin,
 calendar, ymdIST, addDays, addInterval, dateFromYmdIST,
 getCalendarWindow, calTimeRange,
 auditLog
} = require('./_common');""",
            "replace": """const {
 withCors, json, db, admin,
 ymdIST, addDays, addInterval, dateFromYmdIST,
 getCalendarWindow,
 auditLog,
 createStartCalendarEvent
} = require('./_common');""",
            "mode": "replace"
        },
        # BE-2B: Remove local createStartCalendarEvent
        {
            "id": "BE-2B: Remove local createStartCalendarEvent from series_rebuild",
            "search": """async function createStartCalendarEvent({ title, clientId, startDateYmd, dueDateYmd, window }) {
 const cal = calendar();
 const range = calTimeRange(startDateYmd, window.startHH, window.endHH, window.timeZone);
 const res = await cal.events.insert({
 calendarId: 'primary',
 sendUpdates: 'none',
 requestBody: {
 summary: `START: ${title}`,
 description: `ClientId: ${clientId}\\nStart: ${startDateYmd}\\nDue: ${dueDateYmd}`,
 ...range
 }
 });
 return { calendarEventId: res.data.id, calendarHtmlLink: res.data.htmlLink || null };
}""",
            "replace": """// Use shared createStartCalendarEvent from _common.js (supports clientName + calendarDescription)""",
            "mode": "replace"
        },
        # BE-2C: Load clientName once (insert after first = tasks[0].data)
        {
            "id": "BE-2C: Load clientName in series_rebuild",
            "search": """const first = tasks[0].data;""",
            "replace": """const first = tasks[0].data;

// Load client name once (for Calendar description)
const cSnap = first.clientId ? await db().collection('clients').doc(first.clientId).get() : null;
const clientName = (cSnap && cSnap.exists) ? String((cSnap.data() || {}).name || '').trim() : '';
const calendarDescription = String(first.calendarDescription || '').trim();""",
            "mode": "replace"
        },
        # BE-2D: Update calendar event creation call
        {
            "id": "BE-2D: series_rebuild calendar event creation call",
            "search": """const ev = await createStartCalendarEvent({
 title: first.title,
 clientId: first.clientId,
 startDateYmd,
 dueDateYmd,
 window
});""",
            "replace": """const ev = await createStartCalendarEvent({
 title: first.title,
 clientId: first.clientId,
 clientName: clientName || first.clientNameSnapshot || '',
 startDateYmd,
 dueDateYmd,
 window,
 calendarDescription
});""",
            "mode": "replace"
        },
        # BE-2E: Ensure new tasks store clientNameSnapshot/calendarDescription
        {
            "id": "BE-2E: series_rebuild store clientNameSnapshot",
            "search": """await tRef.set({
 ...first,
 occurrenceIndex: idx,
 occurrenceTotal: (first.occurrenceTotal || maxIdx) + n,""",
            "replace": """await tRef.set({
 ...first,
 clientNameSnapshot: (clientName || first.clientNameSnapshot || ''),
 calendarDescription: String(calendarDescription || first.calendarDescription || '').trim(),
 occurrenceIndex: idx,
 occurrenceTotal: (first.occurrenceTotal || maxIdx) + n,""",
            "mode": "replace"
        }
    ]

    # ── BE-3: tasks_bulkimportcsv.js ──
    patches["netlify/functions/tasks_bulkimportcsv.js"] = [
        # BE-3A: Update imports
        {
            "id": "BE-3A: bulkimport imports update",
            "search": """const {
 withCors, json, db, admin,
 calendar, ymdIST, dateFromYmdIST, addDays, addInterval,
 getCalendarWindow, calTimeRange,
 auditLog, asEmailList
} = require('./_common');""",
            "replace": """const {
 withCors, json, db, admin,
 ymdIST, dateFromYmdIST, addDays, addInterval,
 getCalendarWindow,
 auditLog, asEmailList,
 createStartCalendarEvent
} = require('./_common');""",
            "mode": "replace"
        },
        # BE-3B: Remove local createStartCalendarEvent
        {
            "id": "BE-3B: Remove local createStartCalendarEvent from bulkimport",
            "search": """async function createStartCalendarEvent({ title, clientId, startDateYmd, dueDateYmd, window }) {
 const cal = calendar();
 const range = calTimeRange(startDateYmd, window.startHH, window.endHH, window.timeZone);
 const res = await cal.events.insert({
 calendarId: 'primary',
 sendUpdates: 'none',
 requestBody: {
 summary: `START: ${title}`,
 description:
 `ClientId: ${clientId}\\n` +
 `Start: ${startDateYmd}\\n` +
 `Due: ${dueDateYmd}\\n`,
 ...range
 }
 });
 return { calendarEventId: res.data.id, calendarHtmlLink: res.data.htmlLink || null };
}""",
            "replace": """// Use shared createStartCalendarEvent from _common.js (supports clientName + calendarDescription)""",
            "mode": "replace"
        },
        # BE-3C: Pass clientName into calendar creation
        {
            "id": "BE-3C: bulkimport pass clientName to calendar",
            "search": """const ev = await createStartCalendarEvent({
 title, clientId, startDateYmd: startYmd, dueDateYmd: dueYmd, window
});""",
            "replace": """const cSnap = await db().collection('clients').doc(clientId).get();
const cName = cSnap.exists ? String((cSnap.data() || {}).name || '').trim() : '';
const calendarDescription = String(body.calendarDescription || body.googleCalendarDescription || '').trim();

const ev = await createStartCalendarEvent({
 title,
 clientId,
 clientName: cName,
 startDateYmd: startYmd,
 dueDateYmd: dueYmd,
 window,
 calendarDescription
});""",
            "mode": "replace"
        }
    ]

    # ── BE-4: tasks_createone.js ──
    patches["netlify/functions/tasks_createone.js"] = [
        # BE-4A: Define calendarDescription
        {
            "id": "BE-4A: createone define calendarDescription",
            "search": """const isSeries = recurrence !== 'AD_HOC' && generateCount > 1;""",
            "replace": """const calendarDescription = String(body.calendarDescription || body.googleCalendarDescription || '').trim();
const isSeries = recurrence !== 'AD_HOC' && generateCount > 1;""",
            "mode": "replace"
        },
        # BE-4B: Pass clientName/calendarDescription into event creation
        {
            "id": "BE-4B: createone pass clientName to calendar",
            "search": """const ev = await createStartCalendarEvent({
 title, clientId, startDateYmd: startYmd, dueDateYmd: dueYmd, window
});""",
            "replace": """const ev = await createStartCalendarEvent({
 title,
 clientId,
 clientName: clientData.name || '',
 startDateYmd: startYmd,
 dueDateYmd: dueYmd,
 window,
 calendarDescription
});""",
            "mode": "replace"
        },
        # BE-4C: Store snapshot fields on task doc
        {
            "id": "BE-4C: createone store clientNameSnapshot",
            "search": """await tRef.set({
 clientId,
 title,
 category,
 type,
 priority,""",
            "replace": """await tRef.set({
 clientId,
 clientNameSnapshot: String(clientData.name || '').trim(),
 calendarDescription: String(calendarDescription || '').trim(),
 title,
 category,
 type,
 priority,""",
            "mode": "replace"
        }
    ]

    return patches

# ──────────────────────────────────────────────────────────────
# ADVANCED SEARCH — tries multiple strategies
# ──────────────────────────────────────────────────────────────

def advanced_apply_patch(content, patch):
    """
    Try multiple matching strategies to find and replace.
    """
    patch_id = patch["id"]
    search = patch["search"]
    replace = patch["replace"]
    mode = patch.get("mode", "replace")

    log.step(f"Patch: {patch_id}")
    log.indent += 1

    # Strategy 1: Direct string search (handles the code as-is)
    search_stripped = search.strip()
    replace_stripped = replace.strip()

    # Check if already applied
    replace_unique_lines = []
    search_lines_set = set(l.strip() for l in search_stripped.split('\n') if l.strip())
    for l in replace_stripped.split('\n'):
        ls = l.strip()
        if ls and ls not in search_lines_set:
            replace_unique_lines.append(ls)

    if replace_unique_lines:
        # Check first 3 unique lines
        already_count = sum(1 for ul in replace_unique_lines[:3] if ul in content)
        if already_count >= min(2, len(replace_unique_lines[:3])):
            log.skip(f"Already applied: {patch_id}")
            log.indent -= 1
            return content, True

    # Try exact
    idx = content.find(search_stripped)
    if idx != -1:
        log.detail(f"Exact match at position {idx}")
        new_content = content[:idx] + replace_stripped + content[idx + len(search_stripped):]
        log.ok(f"Applied via exact match: {patch_id}")
        log.indent -= 1
        return new_content, True

    # Try line-by-line stripped matching
    log.detail("Exact match failed, trying line-stripped matching...")
    search_lines = [l.strip() for l in search_stripped.split('\n') if l.strip()]

    if search_lines:
        content_lines = content.split('\n')
        for i in range(len(content_lines)):
            if search_lines[0] in content_lines[i].strip() or content_lines[i].strip() == search_lines[0]:
                # Try matching from here
                matched_indices = []
                si = 0
                j = i
                while si < len(search_lines) and j < len(content_lines):
                    cl = content_lines[j].strip()
                    sl = search_lines[si]
                    if cl == '' and sl != '':
                        j += 1
                        continue
                    if cl == sl or sl in cl:
                        # For partial matches, verify it's meaningful
                        if sl in cl:
                            matched_indices.append(j)
                            si += 1
                    else:
                        break
                    j += 1

                if si == len(search_lines) and matched_indices:
                    log.detail(f"Line-stripped match found at lines {matched_indices[0]}-{matched_indices[-1]}")
                    # Get the indentation of the first matched line
                    first_line = content_lines[matched_indices[0]]
                    base_indent = first_line[:len(first_line) - len(first_line.lstrip())]

                    # Build replacement with proper indentation
                    replace_lines = replace_stripped.split('\n')
                    indented_replace = []
                    for rl in replace_lines:
                        rls = rl.strip()
                        if not rls:
                            indented_replace.append('')
                        else:
                            # Determine relative indent from replacement text
                            rl_leading = len(rl) - len(rl.lstrip())
                            # Find min leading in replace to compute relative
                            min_rl = min((len(x) - len(x.lstrip())) for x in replace_lines if x.strip())
                            relative = rl_leading - min_rl
                            indented_replace.append(base_indent + ' ' * relative + rls)

                    # Replace lines from first match to last match
                    start_line = matched_indices[0]
                    end_line = matched_indices[-1]
                    new_lines = content_lines[:start_line] + indented_replace + content_lines[end_line + 1:]
                    new_content = '\n'.join(new_lines)
                    log.ok(f"Applied via line-stripped match: {patch_id}")
                    log.indent -= 1
                    return new_content, True

    # Try regex fuzzy
    log.detail("Line-stripped match failed, trying regex fuzzy...")
    try:
        pattern = make_fuzzy_pattern(search)
        m = re.search(pattern, content, re.DOTALL)
        if m:
            log.detail(f"Regex match at {m.start()}-{m.end()}")
            new_content = content[:m.start()] + replace_stripped + content[m.end():]
            log.ok(f"Applied via regex fuzzy: {patch_id}")
            log.indent -= 1
            return new_content, True
    except re.error as e:
        log.detail(f"Regex error: {e}")

    # Try with collapsed whitespace (most aggressive)
    log.detail("Regex fuzzy failed, trying collapsed whitespace...")
    collapsed_search = re.sub(r'\s+', ' ', search_stripped)
    collapsed_content = re.sub(r'\s+', ' ', content)
    idx = collapsed_content.find(collapsed_search)
    if idx != -1:
        log.detail(f"Found in collapsed form at approx position {idx}")
        # We need to map back to original content positions
        # Count actual characters
        orig_pos = 0
        collapsed_pos = 0
        temp = re.sub(r'\s+', ' ', '')
        # This is complex, so let's try a different approach:
        # Find the first and last distinctive tokens
        tokens = [t for t in search_stripped.split() if len(t) > 3]
        if tokens:
            first_token = tokens[0]
            last_token = tokens[-1]
            first_idx = content.find(first_token)
            last_idx = content.rfind(last_token, first_idx)
            if first_idx != -1 and last_idx != -1:
                end_pos = last_idx + len(last_token)
                # Find end of line for last token
                eol = content.find('\n', end_pos)
                if eol == -1:
                    eol = len(content)
                new_content = content[:first_idx] + replace_stripped + content[eol:]
                log.ok(f"Applied via collapsed whitespace: {patch_id}")
                log.indent -= 1
                return new_content, True

    log.fail(f"ALL strategies failed for patch: {patch_id}")
    log.detail(f"Search text first line: {search_lines[0] if search_lines else 'EMPTY'}")
    log.indent -= 1
    return content, False

# ──────────────────────────────────────────────────────────────
# MAIN ORCHESTRATOR
# ──────────────────────────────────────────────────────────────

def select_folder():
    """Open folder picker dialog."""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    folder = filedialog.askdirectory(
        title="Select the project folder (contains index.html and netlify/functions/)"
    )
    root.destroy()
    return folder


def validate_folder(folder):
    """Check that required files exist."""
    log.step("Validating folder structure...")
    log.indent += 1

    index_path = os.path.join(folder, "index.html")
    has_index = os.path.isfile(index_path)
    log.detail(f"index.html: {'FOUND' if has_index else 'NOT FOUND'}")

    backend_files = [
        "netlify/functions/tasks_updatestatus.js",
        "netlify/functions/series_rebuild.js",
        "netlify/functions/tasks_bulkimportcsv.js",
        "netlify/functions/tasks_createone.js"
    ]

    found = {}
    for bf in backend_files:
        fp = os.path.join(folder, bf)
        exists = os.path.isfile(fp)
        found[bf] = exists
        log.detail(f"{bf}: {'FOUND' if exists else 'NOT FOUND'}")

    log.indent -= 1

    if not has_index:
        log.fail("index.html not found in selected folder!")

    missing = [f for f, e in found.items() if not e]
    if missing:
        log.warn(f"Missing backend files: {missing}")
        log.warn("Will skip patches for missing files.")

    return True


def main():
    log.section("TASK MANAGEMENT APP — PENDING CHANGES PATCHER")
    log.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.blank()

    # ── Select folder ──
    log.step("Opening folder picker...")
    folder = select_folder()
    if not folder:
        log.fail("No folder selected. Exiting.")
        return

    log.info(f"Selected folder: {folder}")
    log.blank()

    # ── Validate ──
    if not validate_folder(folder):
        log.fail("Folder validation failed. Exiting.")
        return

    log.blank()

    # ══════════════════════════════════════════════════════════
    # PHASE 1: UI PATCHES (index.html)
    # ══════════════════════════════════════════════════════════
    log.section("PHASE 1: UI PATCHES (index.html)")

    index_path = os.path.join(folder, "index.html")
    content = read_file(index_path)
    if content is None:
        log.fail("Cannot read index.html. Aborting UI patches.")
    else:
        # Backup
        log.step("Creating backup of index.html...")
        backup_file(index_path)

        original_content = content
        ui_patches = get_ui_patches()

        for patch in ui_patches:
            content, success = advanced_apply_patch(content, patch)
            log.blank()

        if content != original_content:
            write_file(index_path, content)
            log.ok("index.html written with all applied UI patches")
        else:
            log.info("No changes to index.html (all patches skipped or failed)")

    # ══════════════════════════════════════════════════════════
    # PHASE 2: BACKEND PATCHES
    # ══════════════════════════════════════════════════════════
    log.section("PHASE 2: BACKEND PATCHES")

    backend_patches = get_backend_patches()

    for rel_path, patches in backend_patches.items():
        full_path = os.path.join(folder, rel_path)
        log.blank()
        log.section(f"File: {rel_path}")

        if not os.path.isfile(full_path):
            log.warn(f"File not found: {full_path} — skipping all patches for this file")
            for p in patches:
                log.skip(f"Skipped (file missing): {p['id']}")
            continue

        content = read_file(full_path)
        if content is None:
            log.fail(f"Cannot read {rel_path}")
            continue

        # Backup
        log.step(f"Creating backup of {rel_path}...")
        backup_file(full_path)

        original_content = content

        for patch in patches:
            content, success = advanced_apply_patch(content, patch)
            log.blank()

        if content != original_content:
            write_file(full_path, content)
            log.ok(f"{rel_path} written with all applied patches")
        else:
            log.info(f"No changes to {rel_path}")

    # ══════════════════════════════════════════════════════════
    # DONE
    # ══════════════════════════════════════════════════════════
    log.summary()

    # Save log to file
    log_path = os.path.join(folder, f"patch_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    try:
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(log.logs))
        print(f"\n📄 Full log saved to: {log_path}")
    except Exception as e:
        print(f"\n⚠️  Could not save log file: {e}")

    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()