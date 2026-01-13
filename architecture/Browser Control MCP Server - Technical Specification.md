# Browser Instrumentation MCP Server - Technical Specification

## Philosophy

> **This server does not attempt to make browser automation reliable.**
> Browsers are non-deterministic systems. This server prioritizes visibility over convenience.

**Core Principle:** Observation first, action second.

The server is designed around a fundamental asymmetry:
- **INSPECT tools** - Safe, encouraged, no side effects, use freely
- **ACT tools** - Dangerous, require escalation, require justification, logged permanently

Actions don't return success/failure. They return **what was observed** with a confidence level. This reflects the reality that browser automation is inherently uncertain.

---

## Project Overview

A Model Context Protocol (MCP) server for browser **instrumentation** using Playwright. Provides tools for AI assistants to observe and interact with web browsers with full audit trails.

**Core Value Proposition:**
- Observation-first architecture with clear INSPECT/ACT separation
- Session escalation model - actions require explicit permission
- Append-only event log for complete audit trails
- Honest reporting - observed changes, not success/failure
- Clean abstraction for multiple backend implementations

**Target Users:**
- Developers using Claude Desktop, Claude Code, or other MCP clients
- Anyone needing browser observation with AI assistance
- Debugging and inspection workflows, not automation pipelines

**When NOT to Use This:**
- Form filling for real accounts
- Login automation
- Payment flows
- Anything requiring reliable, repeatable automation
- Any scenario you wouldn't trust a flaky intern to perform

For reliable automation, use Playwright directly with proper test infrastructure.

---

## Technical Stack

**Language:** Python 3.11+
**Primary Backend:** Playwright (playwright-python)
**MCP Implementation:** FastMCP from `mcp` package
**Packaging:** Standard Python packaging (pyproject.toml)

**Key Dependencies:**
- `playwright` - Browser automation
- `mcp` - MCP protocol implementation with FastMCP
- `pydantic` - Data validation and models
- `asyncio` - Async support

**Explicitly Not Using:**
- SQLite for Phase 1 (in-memory sessions only)
- Complex state machines
- Success/failure return values

---

## Architecture

### High-Level Component Structure

```
┌─────────────────────────┐
│     MCP Clients         │
│  (Claude Desktop/Code)  │
└───────────┬─────────────┘
            │ MCP Protocol (stdio)
            ▼
┌─────────────────────────┐
│    FastMCP Server       │
│  ┌─────────┬──────────┐ │
│  │ INSPECT │   ACT    │ │
│  │  Tools  │  Tools   │ │
│  │ (safe)  │(escalate)│ │
│  └─────────┴──────────┘ │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│    Browser Manager      │
│  (Session + Event Log)  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│   Playwright Backend    │
│  (Contexts + Pages)     │
└─────────────────────────┘
```

### Key Abstractions

**BrowserManager**
- Manages session lifecycle (create, escalate, destroy)
- Coordinates between server and backend
- Delegates to backend for all operations

**Backend Interface**
- Abstract base class defining INSPECT and ACT operations
- Playwright implementation as primary
- Designed for future extensibility (CDP, Puppeteer)

**Session Model**
- Starts in observation-only mode (`active`)
- Must be explicitly escalated for actions (`escalated`)
- Contains append-only event log
- Tracks console logs and network requests

**Event Log**
- Append-only record of all operations
- Every tool call logged with timestamp
- ACT operations include reason field
- Queryable via `browser_inspect_events`

---

## Session Lifecycle

### States

```
┌──────────┐  escalate   ┌───────────┐
│  ACTIVE  │────────────►│ ESCALATED │
│ (observe)│             │  (act)    │
└────┬─────┘             └─────┬─────┘
     │                         │
     │       destroy           │
     └────────────┬────────────┘
                  ▼
            ┌──────────┐
            │  CLOSED  │
            └──────────┘
```

### Session Creation

Sessions start locked to observation-only mode:

```python
session = await manager.create_session(
    name="research",
    headless=False,
    viewport_width=1280,
    viewport_height=720
)
# Status: ACTIVE (can only use INSPECT tools)
```

### Escalation

To use ACT tools, session must be explicitly escalated with a reason:

```python
result = await manager.escalate_session(
    name="research",
    reason="Need to click login button to test auth flow"
)
# Status: ESCALATED (ACT tools now available)
# Reason permanently logged in event log
```

### Event Logging

Every operation is logged:

```json
[
  {"event_type": "session_created", "timestamp": "...", "details": {"viewport": "1280x720"}},
  {"event_type": "navigate", "timestamp": "...", "details": {"url": "..."}},
  {"event_type": "session_escalated", "timestamp": "...", "reason": "testing auth flow"},
  {"event_type": "click", "timestamp": "...", "reason": "click login", "details": {"selector": "...", "confidence": "medium"}}
]
```

---

## Tool Interface

### Session Management Tools

| Tool | Description | Requires Escalation |
|------|-------------|---------------------|
| `browser_session_create` | Create observation-only session | No |
| `browser_session_list` | List sessions with status | No |
| `browser_session_destroy` | Clean up session | No |
| `browser_session_escalate` | Enable ACT tools (requires reason) | No |

### INSPECT Tools (Safe, Encouraged)

| Tool | Description | Notes |
|------|-------------|-------|
| `browser_inspect_navigate` | Navigate to URL | Sets up observation target |
| `browser_inspect_screenshot` | Capture page image | Returns base64 PNG |
| `browser_inspect_dom` | Get HTML content | Truncates at 100KB |
| `browser_inspect_text` | Get text content | No HTML tags |
| `browser_inspect_console` | Get console logs | Captured since session start |
| `browser_inspect_network` | Get network requests | Method, URL, status |
| `browser_inspect_events` | Get event log | Complete audit trail |

### ACT Tools (Require Escalation + Reason)

| Tool | Description | Returns |
|------|-------------|---------|
| `browser_act_click` | Click element | Observed changes |
| `browser_act_type` | Type into input | Observed changes |
| `browser_act_execute` | Execute JavaScript | Observed changes |

---

## Tool Schemas

### Session Management

```json
{
  "name": "browser_session_create",
  "description": "Create a new browser session for observation. Sessions start in observation-only mode.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "name": {"type": "string", "description": "Unique session name"},
      "headless": {"type": "boolean", "default": false},
      "viewport_width": {"type": "integer", "default": 1280},
      "viewport_height": {"type": "integer", "default": 720}
    },
    "required": ["name"]
  }
}
```

```json
{
  "name": "browser_session_escalate",
  "description": "Escalate session to allow action tools. WARNING: Enables side effects.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "name": {"type": "string"},
      "reason": {"type": "string", "description": "Justification for why actions are needed"}
    },
    "required": ["name", "reason"]
  }
}
```

### INSPECT Tools

```json
{
  "name": "browser_inspect_navigate",
  "description": "Navigate to a URL for observation.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "session": {"type": "string"},
      "url": {"type": "string"}
    },
    "required": ["session", "url"]
  }
}
```

```json
{
  "name": "browser_inspect_events",
  "description": "Get the append-only event log for audit.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "session": {"type": "string"}
    },
    "required": ["session"]
  }
}
```

### ACT Tools

```json
{
  "name": "browser_act_click",
  "description": "Click an element. REQUIRES escalation.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "session": {"type": "string"},
      "selector": {"type": "string", "description": "CSS selector"},
      "reason": {"type": "string", "description": "Why this click is necessary"}
    },
    "required": ["session", "selector", "reason"]
  }
}
```

---

## Action Result Format

ACT tools do NOT return success/failure. They return observed changes:

```json
{
  "action": "click",
  "selector": "#submit-btn",
  "confidence": "medium",
  "observed_changes": {
    "url_changed": true,
    "dom_mutations": 0,
    "network_requests": 3,
    "console_messages": 0,
    "new_url": "https://example.com/submitted"
  },
  "state": {
    "pre_url": "https://example.com/form",
    "post_url": "https://example.com/submitted",
    "pre_title": "Form",
    "post_title": "Success"
  },
  "notes": ""
}
```

### Confidence Levels

| Level | Meaning |
|-------|---------|
| `high` | Strong evidence action had intended effect |
| `medium` | Some observable changes occurred |
| `low` | Uncertain what happened, may have failed |

Confidence is determined by observable signals (URL change, network requests, etc.), not by whether an exception was thrown.

---

## Project Structure

```
browser-control-mcp/
├── src/
│   └── browser_instrumentation_mcp/
│       ├── __init__.py              # Package init, version
│       ├── server.py                # FastMCP server + tool definitions
│       ├── browser_manager.py       # Session lifecycle coordination
│       ├── models.py                # Pydantic models (Event, ActionResult, etc.)
│       └── backends/
│           ├── __init__.py
│           ├── base.py              # Abstract backend interface
│           └── playwright_backend.py # Playwright implementation
├── CLAUDE.md                        # Tool usage guidance for Claude
├── README.md                        # Installation and usage docs
├── pyproject.toml                   # Package configuration
└── .gitignore
```

---

## Data Models

### Session Status

```python
class SessionStatus(str, Enum):
    ACTIVE = "active"      # Observation only
    ESCALATED = "escalated"  # Actions enabled
    CLOSED = "closed"
```

### Event Types

```python
class EventType(str, Enum):
    SESSION_CREATED = "session_created"
    SESSION_DESTROYED = "session_destroyed"
    SESSION_ESCALATED = "session_escalated"
    NAVIGATE = "navigate"
    SCREENSHOT = "screenshot"
    DOM_READ = "dom_read"
    TEXT_READ = "text_read"
    CONSOLE_READ = "console_read"
    NETWORK_READ = "network_read"
    CLICK = "click"
    TYPE = "type"
    EXECUTE = "execute"
    ERROR = "error"
```

### Event

```python
class Event(BaseModel):
    timestamp: datetime
    event_type: EventType
    session: str
    details: dict = {}
    reason: Optional[str] = None  # Required for ACT events
```

### Observed Changes

```python
class ObservedChanges(BaseModel):
    url_changed: bool = False
    dom_mutations: int = 0
    network_requests: int = 0
    console_messages: int = 0
    new_url: Optional[str] = None
```

### Action Result

```python
class ActionResult(BaseModel):
    action: str
    selector: Optional[str] = None
    observed_changes: ObservedChanges
    state: PrePostState
    confidence: Confidence
    notes: str = ""
    timestamp: datetime
```

---

## Backend Interface

```python
class BrowserBackend(ABC):
    # Lifecycle
    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...

    # Session Management
    async def create_session(self, name, headless, viewport_width, viewport_height) -> str: ...
    async def destroy_session(self, name) -> bool: ...
    async def list_sessions(self) -> list[dict]: ...
    async def is_escalated(self, name) -> bool: ...
    async def escalate_session(self, name, reason) -> dict: ...

    # Event Log
    def get_event_log(self, name) -> EventLog: ...
    def log_event(self, event) -> None: ...

    # INSPECT Operations (safe)
    async def navigate(self, session, url) -> dict: ...
    async def screenshot(self, session, full_page) -> bytes: ...
    async def get_dom(self, session, selector) -> dict: ...
    async def get_text(self, session, selector) -> dict: ...
    async def get_console_logs(self, session) -> list[dict]: ...
    async def get_network_logs(self, session) -> list[dict]: ...

    # ACT Operations (require escalation + reason)
    async def click(self, session, selector, reason) -> ActionResult: ...
    async def type_text(self, session, selector, text, reason, clear_first) -> ActionResult: ...
    async def execute_script(self, session, script, reason) -> ActionResult: ...
```

---

## Implementation Status

### Phase 1: Core Foundation (Complete)

- [x] Project structure with FastMCP
- [x] INSPECT/ACT tool separation
- [x] Session escalation model
- [x] Append-only event log
- [x] Observed changes (not success/failure)
- [x] Reason field for ACT tools
- [x] Playwright backend with instrumentation
- [x] Console and network log capture
- [x] README and CLAUDE.md

**Deliverable:** Working MCP server with observation-first architecture

### Phase 2: Persistence (Future)

- [ ] SQLite storage for session metadata
- [ ] Session state serialization
- [ ] Attach to existing sessions
- [ ] Browser user data persistence

### Phase 3: CDP Connection (Future)

- [ ] Connect to already-running browsers
- [ ] Inspect-only mode by default for CDP
- [ ] Escalation required for CDP actions

### Phase 4: Polish (Future)

- [ ] Comprehensive test suite
- [ ] uvx/pip packaging
- [ ] Additional documentation
- [ ] Error recovery patterns

---

## Installation & Usage

### Installation

```bash
git clone https://github.com/yourusername/browser-instrumentation-mcp.git
cd browser-instrumentation-mcp
pip install -e .
playwright install chromium
```

### Claude Desktop Configuration

```json
{
  "mcpServers": {
    "browser": {
      "command": "python",
      "args": ["-m", "browser_instrumentation_mcp.server"]
    }
  }
}
```

### Claude Code Configuration

```bash
claude mcp add browser -- python -m browser_instrumentation_mcp.server
```

---

## Usage Patterns

### Observation Workflow (Typical)

```
1. browser_session_create(name="research")
2. browser_inspect_navigate(session="research", url="example.com")
3. browser_inspect_screenshot(session="research")
4. browser_inspect_text(session="research")
5. browser_inspect_events(session="research")
6. browser_session_destroy(name="research")
```

### Action Workflow (When Necessary)

```
1. browser_session_create(name="test")
2. browser_inspect_navigate(session="test", url="example.com")
3. browser_session_escalate(name="test", reason="testing form submission")
4. browser_act_click(session="test", selector="button", reason="submit form")
5. browser_inspect_events(session="test")  # Audit what happened
6. browser_session_destroy(name="test")
```

---

## Non-Goals

**Explicitly Out of Scope:**

- Reliable, repeatable automation
- Success/failure guarantees
- Form filling workflows
- Login automation
- Payment processing
- Multi-agent coordination
- Complex orchestration logic
- Testing framework integration
- Retry/recovery mechanisms

This server is for **observation with occasional, justified action** - not for automation pipelines.

---

## Design Rationale

### Why No Success/Failure?

Browsers are non-deterministic. A click might:
- Work perfectly
- Work but trigger unexpected navigation
- Fail silently
- Throw an exception but still work
- Work on the wrong element

Reporting "success: true" would be lying. Instead, we report what we observed and let the caller decide.

### Why Escalation?

Friction is intentional. If using ACT tools is annoying, that's the point. It forces:
- Conscious decision to enable actions
- Clear justification (logged permanently)
- Preference for observation over action

### Why Append-Only Log?

Trust requires auditability. The event log:
- Cannot be modified or deleted
- Records every operation with timestamp
- Includes reasons for all actions
- Enables post-hoc analysis of what happened

---

## References

- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [Playwright Python Docs](https://playwright.dev/python/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)

---

## Claude Code Guidance

When using this MCP server:

1. **Prefer `browser_inspect_*` tools** - Use these by default
2. **Use `browser_act_*` tools only when observation is insufficient**
3. **Always explain why action is necessary** before escalating
4. **Check the event log** to understand what happened
5. **Don't trust action results** - verify with observation tools
