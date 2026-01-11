# Local‑First Dual‑Pane Terminal

## Purpose
A calm, local‑first terminal environment designed for serious solo work. The terminal remains ground truth. AI is present only as an explicit, non‑authoritative aid. No accounts, no OAuth dependencies, no hidden meters.

This tool optimizes for continuity, trust, and cognitive clarity rather than onboarding speed or collaboration metrics.

---

## Design Principles

1. **Shell is Law**
   The terminal pane represents reality. Commands execute exactly as typed. No AI ever runs commands implicitly.

2. **AI Is Commentary, Not Action**
   AI may suggest, analyze, or transform text, but never executes without explicit user intent.

3. **Local‑First by Default**
   The system functions fully offline. Cloud models are optional, additive, and clearly separated.

4. **Explicit Seams**
   Users always know which component is acting: shell, local model, or remote model.

5. **Boring Is Correct**
   Predictable behavior is preferred over clever automation.

---

## High‑Level Architecture

The application consists of three concurrent components:

1. Terminal Pane (Primary)
2. Thinking Pane (Secondary)
3. Local Model Worker (Background)

Each component has a clearly defined role and interaction boundary.

---

## UI Layout

The default layout is a split interface:

- **Left Pane**: Terminal
- **Right Pane**: Thinking Pane (Claude or other cloud model)
- **Optional Bottom Strip**: Status / Context Panel

No AI input replaces the terminal prompt.

---

## Component Specifications

### 1. Terminal Pane

**Role:** Ground truth execution environment.

**Responsibilities:**
- Execute shell commands
- Display stdout/stderr
- Maintain session state
- Respect exit codes

**Constraints:**
- No natural‑language input
- No AI‑generated commands auto‑executed
- No mutation without direct user input

---

### 2. Thinking Pane (Cloud Model)

**Role:** Sensemaking and reflection.

**Responsibilities:**
- Architecture reasoning
- Log interpretation
- Diff review
- Strategy discussion
- Error analysis

**Constraints:**
- Never executes commands
- Never mutates files directly
- Requires explicit user confirmation to apply suggestions

**Authentication:**
- User‑provided credentials
- Clearly labeled as optional
- Failure does not affect terminal functionality

---

### 3. Local Model Worker

**Role:** Fast, bounded utility tasks.

**Responsibilities:**
- Summarization
- Refactoring suggestions
- Linting output interpretation
- Text transformations

**Constraints:**
- No autonomy
- No implicit triggers
- Invoked explicitly via commands or keybindings

---

## Interaction Model

All AI interaction is explicit and user‑initiated.

Examples:
- Select terminal output → Send to Thinking Pane
- Select file or diff → Send to Local Model
- Ask Thinking Pane for suggested commands → User manually copies or applies

No background agents. No silent chains.

---

## Command Routing (Conceptual)

AI commands use distinct prefixes or UI actions that cannot be confused with shell commands.

Examples:
- `>>` Send selection to Thinking Pane
- `~>` Send selection to Local Model
- `!>` Ask for suggested commands (non‑executing)

These prefixes never overlap with shell syntax.

---

## Status & Transparency Panel

Displays:
- Which models are active
- Online/offline state
- Current context scope
- Explicit failures or timeouts

No hidden usage meters.

---

## Authentication & Access Philosophy

### No OAuth as a Foundation

This system does **not** rely on OAuth or account‑based authentication for core functionality. The terminal, local model worker, and UI operate fully without login.

OAuth is explicitly **not** treated as a stable foundation or dependency.

### Respect Existing Sessions

If the user is already authenticated through an external official application (for example, a provider‑supplied CLI or desktop app such as Claude Code), this tool may:
- Detect and reuse existing local session credentials
- Delegate requests to the provider’s official client
- Operate as a pass‑through surface

No authentication is initiated, refreshed, or managed by this application.

### Design Rule

- The terminal never requires login
- AI panes degrade gracefully if credentials are unavailable
- Loss of authentication never breaks local workflows

Authentication is treated as **ambient state**, not infrastructure.

---

## Non‑Goals

The system intentionally does **not** include:
- Account systems
- OAuth‑based core functionality
- Cloud sync
- Plugin marketplaces
- Agentic automation
- Implicit AI suggestions

---

## Failure Philosophy

- If AI fails, the terminal continues.
- If network access is lost, the system remains usable.
- If credentials expire, only the affected pane degrades.

Failure is visible, local, and non‑catastrophic.

---

## Success Criteria

This tool is successful if:
- The user forgets about pricing and limits while working
- The terminal feels timeless
- AI never surprises the user
- The system feels calm rather than clever

If it feels boring, it is working correctly.

