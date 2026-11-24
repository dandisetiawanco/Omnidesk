# OmniDesk Architecture

OmniDesk separates the native desktop shell, shared schemas, AI planning layer, security policy boundary, and deterministic automation executors into isolated components.

## High-Level Topology

```
+-------------------------------------------------------------------+
|  Tauri 2 Native Shell (Rust: apps/desktop/src-tauri)              |
|  - OS Platform Adapters (macOS / Windows / Linux)                 |
|  - Real Hardware, Display & Permission Capability Registry        |
|  - OS Secure Credential Vault (keyring crate)                     |
|  - Native Window Vibrancy / Mica / Solid Fallback                 |
|  - System Tray, Global Shortcut & Backend Process Lifecycle       |
|  - Generates 256-bit CSPRNG Session Token (OMNIDESK_SESSION_TOKEN)|
+------------------------+------------------------------------------+
                         | Tauri IPC (token + native dialogs)
                         v
+-------------------------------------------------------------------+
|  Omni Glass Frontend (React 19 + TypeScript + Vite)               |
|  - Lazy-loaded Views (Home, Operator, Live, Studio, Teach, ...)   |
|  - Global Command Palette & Approval <dialog> Top-Layer Overlays  |
|  - Authenticated Fetch + ReadableStream SSE Client                |
+------------------------+------------------------------------------+
                         | HTTP / SSE on 127.0.0.1 (Bearer Token)
                         v
+-------------------------------------------------------------------+
|  Local Operator Engine (Python 3.12 + FastAPI + SQLite + Pydantic)|
|  - TaskPlanner: Local Deterministic + Configured Model Adapters   |
|  - Security Policy Gate: Deny-by-Default Risk & Path Scoping      |
|  - TaskOrchestrator: Bounded Async Queue, Pause/Resume/Stop       |
|  - Operation Journal: SHA-256 Verified Rollback for File Moves    |
|  - Automation Tools: Filesystem, OpenPyXL, Playwright, Apps       |
|  - WorkflowRunner & TeachModeEngine                               |
|  - MCP JSON-RPC 2.0 Interoperability Endpoint                     |
+-------------------------------------------------------------------+
```

## Modular Repository Structure

| Path | Responsibility |
| --- | --- |
| `packages/shared-schemas` | TypeScript + Zod contracts shared across frontend and tests |
| `apps/desktop/src` | React UI, Omni Glass CSS layers, state, and interactive views |
| `apps/desktop/src-tauri` | Rust desktop shell, platform adapters, tray, keyring, vibrancy |
| `backend/omnidesk_engine/security` | Risk policy engine, path scoping, prompt-injection isolation, credential vault, operation journal |
| `backend/omnidesk_engine/providers` | Ollama, OpenAI, Google Gemini, Anthropic Claude, OpenAI-compatible adapters |
| `backend/omnidesk_engine/intelligence` | Structured task planner and async execution orchestrator |
| `backend/omnidesk_engine/automation` | Filesystem, Excel `.xlsx`, Markdown reports, Playwright browser, native app launch, clipboard, opt-in vision |
| `backend/omnidesk_engine/workflows` | Versioned DAG workflow runner and Flagship Teach Mode synthesizer |
| `backend/omnidesk_engine/mcp` | Model Context Protocol (MCP) JSON-RPC bridge |

## Structured Execution Pipeline

Every task follows a deterministic, auditable state machine:

1. **Natural Language Request**: User submits a command or runs a workflow.
2. **Context Collection**: Scoped directory, privacy policy, and available capabilities are resolved.
3. **Task Planning**: Configured model (if permitted) or built-in deterministic planner produces typed `ActionStep` definitions.
4. **Policy Validation**: Every step is classified against `TOOL_POLICIES` outside the model. Destructive and privileged shell tools are blocked by default.
5. **Dry-Run & Approval**: Modifying or external actions compute a dry-run preview and pause in `awaiting_approval` until explicitly approved.
6. **Execution & Journaling**: Approved mutations verify paths and record SHA-256 digests in `operation_journal`.
7. **Verification & Completion**: Outputs and artifacts are verified on disk and persisted in indexed SQLite history.

## Extensibility for Future Releases

The architecture keeps clean extension seams for future team workflows, plugin SDK tool registration, encrypted optional sync, scheduled triggers, and enterprise policy enforcement without bundling subscriptions or authentication bloat into the standalone local MVP.
