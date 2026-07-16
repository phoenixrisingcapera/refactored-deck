# Deck AI Stack — Consolidation Judgment

**Date:** 2026-07-16
**Author:** Architecture analysis from live codebase inspection
**Status:** Pre-implementation analysis. No code changed.

---

## 1. What Was Inspected

Both production repositories were cloned and deep-read:

- **Backend:** `phoenixrisingcapera/deck-Aistack-backend-new` (941 files)
- **Frontend:** `phoenixrisingcapera/deck-Aistack-front-new`

Every file under `app/api/routes/`, `app/services/`, `app/ai_orchestration/`, `app/workers/`, `app/db/models/`, `src/routes/`, `src/lib/api/`, `src/lib/components/`, `src/lib/features/`, and `src/lib/server/` was inspected. The findings below reference real file paths and line numbers.

---

## 2. Executive Summary

The product has **three separate execution authorities** that all claim to own "AI generation":

1. **`app/ai_orchestration/`** — A synchronous orchestrator (`SmartDeckOrchestrator`) with its own provider system (`BaseLlmProvider`), its own data model (`AiRun`, `AiRunStep`), and its own route (`POST /ai/orchestrate`). This runs LLM calls directly in the request path.

2. **`app/services/deck_processing/workflow_jobs.py`** — A durable `WorkflowJob` system with 13 job types, worker dispatch, heartbeat, and recovery. This is the only system that can survive worker restarts.

3. **`app/services/llm/smart_edit_service.py` and `app/services/llm/due_diligence_service.py`** — Feature services that call LLM providers synchronously within the HTTP request, bypassing both orchestration systems.

These three systems share the same database, the same LLM providers, and the same frontend — but they do not share a control plane. The result is competing state owners, duplicate provider resolution, and inconsistent error handling.

**The product works.** But every new feature must be wired into three separate systems, and there is no single place to answer "what is this deck's current AI state?"

---

## 3. Backend Architecture Map

### 3.1 Route Inventory (100+ endpoints)

**Mounted in `app/main.py`:**

| Mount method | Prefix | Routers |
|---|---|---|
| Direct `include_router` | `/api` | health, account, billing, auth, assistant, deck_map, deck_processing_pipeline |
| Direct `include_router` | `/api/products/deck-aistack-codes` | public_interest |
| `PRODUCT_ROUTERS` loop | `/api` | 20 routers (see below) |
| `ADMIN_PROTECTED_ROUTERS` loop | `/api` | 8 admin routers |
| `ADMIN_PUBLIC_ROUTERS` loop | `/api` | failure_tickets |

**`PRODUCT_ROUTERS` (from `app/api/routes/product/__init__.py:35-59`):**

| # | Router | Tags | Domain |
|---|---|---|---|
| 1 | `upload_rescue_router` | upload-rescue | Upload recovery |
| 2 | `product_upload_compat_router` | products | Upload compatibility |
| 3 | `deck_retry_rescue_router` | deck-retry-rescue | Deck recovery |
| 4 | `deck_artifacts_router` | deck-artifacts | LLM artifact listing |
| 5 | `product_intake_cleanup_router` | products | Intake cleanup |
| 6 | `product_processing_router` | product-processing | Processing status |
| 7 | `products_router` | products | Upload, workspace summary |
| 8 | `agent_capabilities_router` | agent-capabilities | Agent capabilities |
| 9 | **`ai_orchestration_router`** | deck-aistack-codes-ai | **Competing orchestration** |
| 10 | `deck_intake_router` | deck-intake | Intake status, structure extraction |
| 11 | `deck_workflow_router` | deck-workflow | Workflow state, commands |
| 12 | `shell_router` | shell | Deck graph, slides, batches |
| 13 | `brand_extraction_router` | brand-extraction | Brand extraction |
| 14 | `deck_generation_router` | deck-generation | Generation workspace, slide gen |
| 15 | `decks_router` | decks | CRUD, analysis, smart-edit, adapt, iterations |
| 16 | `slides_router` | slides | Slide listing, previews |
| 17 | `smart_deck_router` | smart-deck | Smart Deck workspace, messages, design versions |
| 18 | `suggestions_router` | suggestions | Suggestion accept/dismiss/edit |
| 19 | `exports_router` | exports | Export create, list, download |
| 20 | `product_analytics_router` | products | Analytics events |
| 21 | `product_developer_tools_router` | products | Developer tools |
| 22 | `workspace_ai_provider_router` | workspace-ai-provider | AI provider config CRUD |
| 23 | `workspace_dashboard_router` | workspace-dashboard | Dashboard |
| 24 | `product_runtime_hardening_router` | product-runtime-hardening | Hardened status endpoints |

**Additional direct mounts:**
- `assistant_router` at `/api` (assistant/LLM chat)
- `deck_map_router` at `/api` (deck map, market research)
- `deck_processing_router` at `/api` (processing pipeline)

### 3.2 Service Layer (100+ service files)

| Directory | Files | Domain |
|---|---|---|
| `app/services/llm/` | 41 files | LLM providers, generation, smart-edit, due-diligence, embeddings, retrieval, vision, critique, repair |
| `app/services/deck_processing/` | 25 files | Workflow jobs, orchestration, state machine, upload, extraction, brand, context |
| `app/services/admin/` | 19 files | Admin operations, telemetry, diagnostics, repair, guardrails |
| `app/services/storage/` | 9 files | Object storage (local/S3/Supabase), signed URLs, security scanning |
| `app/services/brand/` | 10 files | Brand extraction, enrichment, profiles |
| `app/services/rendering/` | 5 files | Render schema, validation, export, final deck |
| `app/services/agents/` | 6 files | Agent registry, smart-deck/edit/due-diligence agents |
| `app/services/visualizer/` | 7 files | Read models for generated decks, slides, iterations |
| `app/services/platform/` | 4 subdirs | Auth, billing, shell/workspace, admin |
| `app/services/generation/` | subdir | Generation services |
| `app/services/training/` | subdir | Training export |

### 3.3 Worker System (durable, poll-based)

**Entry:** `scripts/deck_processing_worker.py` -> `app/workers/entrypoints/worker_entrypoint.py`

**13 job types dispatched by `app/workers/dispatch/job_handlers.py:28-86`:**

| Job Type | Handler Module | Purpose |
|---|---|---|
| `source_ingestion` | `runtime.source_pipeline_runtime` | Upload ingestion |
| `source_extraction` | same | Structure extraction |
| `miniatures` | same | Thumbnail generation |
| `brand_extraction` | same | Brand profile extraction |
| `smart_deck_context` | same | Context building for Smart Deck |
| `llm_generation` | `runtime.generation_runtime` | LLM slide generation |
| `selected_slide_generation` | `runtime.selected_slide_generation_runtime` | Single-slide generation |
| `schema_validation` | `runtime.generation_runtime` | Render schema validation |
| `preview_render` | same | Preview rendering |
| `apply_version` | same | Design version application |
| `compile_final_deck` | same | Final deck compilation |
| `db_publisher` | `runtime.publisher_runtime` | Database state publishing |
| `export` | same | Export file generation |

**Worker kinds map to job types via `app/workers/dispatch/worker_runtime_service.py:54-69`.**

Dedicated worker entrypoints exist for: source, generation, render, export, rescue (stale job recovery).

### 3.4 Database Models (50+ models across two databases)

**Core database (product state):**

| Model | Table | Purpose |
|---|---|---|
| `User` | users | Authentication |
| `Deck` | decks | Core entity |
| `DeckSlide` | deck_slides | Extracted slides |
| `DeckSlideBlock` | deck_slide_blocks | Text blocks |
| `DeckSlideAsset` | deck_slide_assets | Visual assets |
| `WorkflowJob` | workflow_jobs | Durable job queue |
| `WorkflowJobEvent` | workflow_job_events | Job lifecycle events |
| `DeckLlmArtifact` | deck_llm_artifacts | Immutable AI output envelope |
| `DesignVersion` | design_versions | Smart Deck design snapshots |
| `DesignBatch` | design_batches | Batch generation runs |
| `GeneratedSlide` | generated_slides | LLM-generated slides |
| `SmartDeckWorkspace` | smart_deck_workspaces | Smart Deck state |
| `SmartDeckMessage` | smart_deck_messages | Chat messages |
| `SmartEditRun` | smart_edit_runs | Smart Edit execution history |
| `SmartEditSuggestion` | smart_edit_suggestions | Smart Edit review objects |
| `ChangeRequest` | change_requests | **Competing** review model |
| `DeckExport` | deck_exports | Export records |
| `WorkspaceAiProviderSetting` | workspace_ai_provider_settings | Provider config |
| `AnalysisRun` | analysis_runs | Analysis execution |
| `AnalysisFinding` | analysis_findings | Analysis results |

**AI database (embeddings, telemetry):**

| Model | Table | Purpose |
|---|---|---|
| `VectorChunk` | vector_chunks | pgvector embeddings |
| `AiRun` | ai_runs | **Competing** AI run model |
| `AiRunStep` | ai_run_steps | **Competing** AI run steps |
| `ProductEvent` | product_events | Analytics |
| `DeckTelemetryEvent` | deck_telemetry_events | Telemetry |
| `TrainingExport` | training_exports | Training data |

### 3.5 Provider System (two competing implementations)

**Service-level providers (`app/services/llm/`):**

| Provider | File | Used By |
|---|---|---|
| `DashScopeProvider` | `dashscope_provider.py:329` | generation_service, smart_edit_service, due_diligence_service |
| `OpenAIProvider` | `openai_provider.py` | Same |
| `AnthropicProvider` | `anthropic_provider.py` | Same |
| `OpenRouterProvider` | `openrouter_provider.py` | Same |

Resolution: `app/services/llm/provider_registry.py` (singleton registry)

**Orchestration-level providers (`app/ai_orchestration/providers/`):**

| Provider | File | Used By |
|---|---|---|
| `DashScopeLlmProvider` | `dashscope_provider.py` | SmartDeckOrchestrator |
| `OpenAiLlmProvider` | `openai_provider.py` | Same |
| `AnthropicLlmProvider` | `anthropic_provider.py` | Same |
| `OpenRouterLlmProvider` | `openrouter_provider.py` | Same |

Resolution: `app/ai_orchestration/provider_resolver.py` (workspace config or env)

**These are separate class hierarchies with separate resolution logic.** The Qwen strategy (`app/services/llm/qwen_strategy.py`) only applies to the service-level providers.

---

## 4. Frontend Architecture Map

### 4.1 Route Table (60+ routes)

**Marketing/Public (8 routes):**
- `/`, `/about`, `/pricing`, `/contact`, `/privacy`, `/terms`, `/vcs`, `/billing`

**Auth (7 routes):**
- `/auth/sign-in`, `/auth/sign-up`, `/auth/callback`, `/auth/success`
- `/sign_in_landing` (redirect), `/sign-in` (redirect), `/sign-up` (redirect)

**Product (30+ routes):**
- `/welcome`, `/dashboard`, `/decks`, `/decks/new`
- `/decks/[deckId]`, `/decks/[deckId]/processing`
- `/decks/[deckId]/smart-deck`, `/decks/[deckId]/smart-edit`
- `/decks/[deckId]/due-diligence`, `/decks/[deckId]/diligence` (alternate)
- `/decks/[deckId]/export`, `/decks/[deckId]/slides`
- `/decks/[deckId]/batches`, `/decks/[deckId]/batches/[batchId]`, `/decks/[deckId]/batches/[batchId]/compile`
- `/decks/[deckId]/iterations`, `/decks/[deckId]/iterations/[iterationId]`, `/decks/[deckId]/iterations/[iterationId]/compile`
- `/decks/[deckId]/compiled/[compiledDeckId]`
- `/decks/[deckId]/changes` (redirect only)
- `/decks/[deckId]/audience`
- `/smart-deck`, `/smart-edit` (global, without deckId)
- `/exports`, `/templates`, `/datasets`, `/insights`, `/team`
- `/settings`, `/settings/account/settings`, `/settings/account/connected-accounts`
- `/settings/account/conected-accounts` (**typo path** — exists as server-only redirect)
- `/app/billing`

**Admin (25+ routes):** All redirect to external admin console.
- `/admin`, `/admin/users`, `/admin/agents`, `/admin/agents/[runId]`
- `/admin/agent-teams`, `/admin/learning`, `/admin/llm-knowledge`
- `/admin/llm-workflows`, `/admin/training`, `/admin/audit`
- `/admin/testers`, `/admin/safety-controls`, `/admin/quotas`
- `/admin/telemetry`, `/admin/provider-health`, `/admin/deployment-readiness`
- `/admin/failure-tickets`, `/admin/failure-tickets/[ticketId]`
- `/admin/processing/[deckId]`, `/admin/processing/jobs`
- `/admin/slides/[deckId]`, `/admin/elements`
- `/admin/decks/[deckId]/smart-deck`
- `/super-admin/*` (all redirect)

### 4.2 API Client Layer

| Client File | Domain | Key Functions |
|---|---|---|
| `src/lib/api/deckServiceClient.ts` | Workspace, upload, provider | `getWorkspaceSummary()`, `uploadFirstDeck()`, `saveWorkspaceAiProvider()` |
| `src/lib/api/auth.ts` | Authentication | `validateSession()`, `signIn()`, `signUp()` |
| `src/lib/api/smartDeckWorkspace.ts` | Smart Deck | `getSmartDeckWorkspace()`, `startSmartDeckGenerationWorkflow()`, `applyDesignVersion()` |
| `src/lib/api/deckService/workflow.client.ts` | Workflow status | `getDeckWorkflowStatus()`, `waitForWorkflowJobCompletion()` |
| `src/lib/server/backendApi.ts` | Generic proxy | `proxyBackendJson()` |
| `src/lib/server/adminApi.ts` | Admin | 30+ admin functions |
| `src/lib/server/auth/authService.ts` | Server auth | `signInOrUp()`, `completeCallback()` |
| `src/lib/server/load-smart-deck-page.ts` | Smart Deck loader | Orchestrates 7+ backend calls |

**No unified API client exists.** Smart Edit and Due Diligence page components make direct `fetch` calls without going through a shared client.

### 4.3 Competing Frontend Implementations

**Smart Deck:**
- `UserSmartDeckWorkspace` (active, in `src/lib/features/smart-deck/user/`)
- `SmartDeckWorkspace` (legacy, in `src/lib/components/smart-deck/`)
- The page at `src/routes/(product)/decks/[deckId]/smart-deck/+page.svelte` imports both, uses `UserSmartDeckWorkspace`

**Smart Edit:**
- Entire implementation lives in the page component (1237 lines)
- No dedicated feature component or API client
- Makes direct `fetch` calls to multiple backend endpoints
- Normalizes multiple response shapes inline

**Due Diligence:**
- Entire implementation lives in the page component (1034 lines)
- No dedicated feature component or API client
- Makes direct `fetch` calls
- Handles multiple audience types inline

---

## 5. The Three Competing Execution Authorities

### Authority 1: `ai_orchestration` (synchronous, in-request)

```
POST /api/products/deck-aistack-codes/ai/orchestrate
  -> SmartDeckOrchestrator.run()
    -> SmartDeckContextBuilder (context)
    -> BaseLlmProvider.generate_slide_versions() (LLM call, synchronous)
    -> SceneGraphValidator (validation)
    -> Persist AiRun, AiRunStep, DeckLlmArtifact, DesignBatch, GeneratedSlideCandidate
  -> Return AiOrchestrationResponse
```

**Problems:**
- Runs LLM calls in the HTTP request path (blocks for 10-60+ seconds)
- Uses its own provider hierarchy (`BaseLlmProvider`) separate from the service providers
- Creates `AiRun` and `AiRunStep` records that compete with `WorkflowJob` for "what is the current AI state"
- No heartbeat, no recovery, no worker dispatch
- Frontend must poll or wait for a long-running HTTP response

### Authority 2: `workflow_jobs` (durable, worker-dispatched)

```
POST /api/deck-generation/{deck_id}/generate-slides
  -> Create WorkflowJob (type=llm_generation)
  -> Worker claims job
    -> handle_llm_generation()
      -> generation_service (uses service-level LLMProvider)
      -> Persist GeneratedSlide, DesignVersion
    -> Next job: schema_validation -> preview_render -> db_publisher
  -> Frontend polls workflow state
```

**This is the correct architecture.** It survives worker restarts, has heartbeat, has recovery, and separates enqueue from execution.

### Authority 3: Feature services (synchronous, in-request, no orchestration)

```
POST /api/decks/{deck_id}/smart-edit
  -> smart_edit_service.run_smart_edit()
    -> Provider call (synchronous)
    -> Persist SmartEditRun, SmartEditSuggestion, DeckLlmArtifact
  -> Return suggestion for review

POST /api/decks/{deck_id}/due-diligence (or /api/deck-intake/{deck_id}/due-diligence-workspace)
  -> due_diligence_service.extract_due_diligence_claims() / analyze_due_diligence_risks() / build_due_diligence_report()
    -> Provider call (synchronous)
    -> Persist DeckLlmArtifact
  -> Return report
```

**Problems:**
- Both Smart Edit and Due Diligence run LLM calls in the request path
- Neither uses `WorkflowJob` for execution
- Neither has heartbeat or recovery
- Smart Edit creates `SmartEditRun` + `SmartEditSuggestion` (separate from `AiRun`)
- Due Diligence creates `DeckLlmArtifact` with different artifact types (no run identity)

---

## 6. The Identity Crisis

Three separate models claim to represent "an AI generation run":

| Model | Table | Created By | Used For |
|---|---|---|---|
| `AiRun` | ai_runs (AI DB) | `ai_orchestration.orchestrator` | Smart Deck orchestration |
| `SmartEditRun` | smart_edit_runs (Core DB) | `smart_edit_service` | Smart Edit execution |
| `WorkflowJob` | workflow_jobs (Core DB) | `workflow_orchestration` | All durable jobs |

And for "a reviewable AI output":

| Model | Table | Created By | Used For |
|---|---|---|---|
| `GeneratedSlideCandidate` | generated_slide_candidates | `ai_orchestration` | Smart Deck batch review |
| `DesignVersion` | design_versions | `workflow_jobs` pipeline | Smart Deck design versions |
| `SmartEditSuggestion` | smart_edit_suggestions | `smart_edit_service` | Smart Edit review |
| `ChangeRequest` | change_requests | `deck_processing_pipeline` route | **Competing** Smart Edit review |
| `DeckLlmArtifact` | deck_llm_artifacts | Multiple services | General AI output envelope |

**Five competing review objects.** The frontend must translate between all of them.

---

## 7. What the Frontend Actually Calls

Tracing from each frontend page to its backend endpoint:

| Frontend Page | Backend Endpoint | Execution Path |
|---|---|---|
| Smart Deck | `POST /ai/orchestrate` | **Sync orchestrator** (AiRun) |
| Smart Deck (generation) | `POST /deck-generation/{id}/generate-slides` | **WorkflowJob** (durable) |
| Smart Deck (apply) | `POST /ai/orchestrate` with apply mode | **Sync orchestrator** |
| Smart Edit | `POST /decks/{id}/smart-edit` | **Sync service** (SmartEditRun) |
| Due Diligence | `POST /deck-intake/{id}/due-diligence-workspace` | **Sync service** (DeckLlmArtifact) |
| Processing | `GET /deck-workflow/{id}/state` | **WorkflowJob** read model |
| Export | `POST /decks/{id}/export` | **WorkflowJob** (durable) |
| Upload | `POST /products/.../create-first-deck-upload` | **WorkflowJob** (durable) |

**The product currently uses all three execution authorities simultaneously.** Smart Deck is split between the sync orchestrator and the durable workflow. Smart Edit and Due Diligence are entirely synchronous.

---

## 8. Judgment: How to Consolidate

### 8.1 What to keep as canonical

**One control plane: `workflow_jobs`**

The `WorkflowJob` system is the only production-grade execution authority. It has:
- Durable state in PostgreSQL
- Worker heartbeat and recovery
- Job dependencies (pipeline sequencing)
- Stale job rescue
- Per-kind worker entrypoints
- 13 job types already defined

**Everything else must report to it.**

### 8.2 What to consolidate (in priority order)

**Phase 1: Smart Edit -> WorkflowJob**

Current state: `smart_edit_service.py` (1050 lines) runs synchronously.
Target state: Smart Edit becomes a WorkflowJob type with steps:
1. `smart_edit_resolve_target`
2. `smart_edit_build_context`
3. `smart_edit_retrieve`
4. `smart_edit_classify_and_generate`
5. `smart_edit_validate`
6. `smart_edit_persist_review`

Canonical review object: **`SmartEditSuggestion`** (already used by the frontend).
Disable: `ChangeRequest` as a competing review path (keep as compatibility if frontend still references it).

**Phase 2: Due Diligence -> WorkflowJob**

Current state: `due_diligence_service.py` (213 lines) runs synchronously.
Target state: Due Diligence becomes a WorkflowJob type with steps:
1. `diligence_context`
2. `diligence_extract_claims`
3. `diligence_retrieve_evidence`
4. `diligence_financial_validation`
5. `diligence_audience_analysis`
6. `diligence_risk_analysis`
7. `diligence_build_report`

Canonical identity: `DeckLlmArtifact` with `artifact_type` discrimination (already exists).
Add: `AnalysisRun` as the run-level identity (already exists in the models).

**Phase 3: Smart Deck ai_orchestration -> WorkflowJob**

Current state: `SmartDeckOrchestrator` runs synchronously via `POST /ai/orchestrate`.
Target state: The existing `llm_generation` / `selected_slide_generation` WorkflowJob types already handle this. The `/ai/orchestrate` route becomes a thin enqueue adapter that creates a WorkflowJob and returns 202.

Canonical review object: **`DesignVersion`** (already used by the workflow pipeline).
Disable: `AiRun` as a competing production root (keep as compatibility read model).

**Phase 4: Provider Gateway**

Current state: Two separate provider hierarchies with separate resolution.
Target state: One `provider_gateway.py` under `app/product_runtime/ai/` that:
- Resolves workspace config or env
- Selects the provider class
- Routes by operation type (generation, critique, repair, embedding, vision)
- Returns typed `ProviderResult`
- Is the only import point for canonical workflows

Keep: Service-level provider classes as low-level adapters.
Disable: `ai_orchestration/providers/` as a separate hierarchy.

**Phase 5: Frontend consolidation**

Current state: Smart Deck has two workspace components. Smart Edit and Due Diligence are 1000+ line page components with inline API calls.
Target state:
- `src/lib/features/deck-product/` as the single feature root
- One API client per feature domain
- Page components become thin loaders + command adapters
- Smart Edit and Due Diligence get dedicated components extracted from their page files

### 8.3 What NOT to do

- Do not create a new orchestration framework. `WorkflowJob` is the answer.
- Do not create a new artifact model. `DeckLlmArtifact` is the answer.
- Do not create a new provider abstraction. The service-level `LLMProvider` hierarchy is the answer.
- Do not move all code into one folder. Keep `app/api/routes/`, `app/services/`, `app/workers/` as separate concerns.
- Do not delete any existing routes, models, or tables during consolidation. Disable execution, preserve code.
- Do not rewrite Smart Deck, Smart Edit, or Due Diligence. Move them onto the existing durable workflow.

### 8.4 The target state

A developer should be able to explain every product action as:

```
Frontend command
  -> Canonical typed route (thin adapter)
    -> WorkflowJob created (type + metadata)
      -> Worker claims job
        -> Named workflow step (function)
          -> One provider gateway call
            -> Validated immutable result
              -> User reviews (DesignVersion / SmartEditSuggestion / DeckLlmArtifact)
                -> Atomic apply
                  -> Persisted version + audit
```

There must be **one explanation** for each action, not three.

---

## 9. Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Smart Edit sync path has unique capabilities not in WorkflowJob | High | Map every capability before migration; preserve unique logic in workflow steps |
| Due Diligence deletes prior findings before replacement succeeds | High | Add "persist new, then swap" pattern; never delete before new is validated |
| Frontend Smart Deck page calls both `/ai/orchestrate` and `/deck-generation/` | Medium | Trace exact frontend call paths; convert `/ai/orchestrate` to enqueue-only |
| `AiRun` records are read by admin dashboard | Medium | Keep `AiRun` as a read model; stop writing new records from canonical path |
| `ChangeRequest` is used by deck_processing_pipeline route | Medium | Verify if frontend references it; if so, make it a thin adapter over SmartEditSuggestion |
| Provider resolution differs between service and orchestration layers | High | Unified gateway must produce identical results; test with both workspace config and env |
| Worker restart during Smart Edit migration could lose in-flight state | Medium | WorkflowJob already handles this; migration adds durability |

---

## 10. Recommended PR Sequence

Each PR is limited to one capability. Each must pass all existing tests before merge.

| # | PR | Scope | Risk |
|---|---|---|---|
| 1 | Architecture guardrail tests | Add tests that fail if: route disappears, duplicate method/path appears, canonical route calls LLM directly | None |
| 2 | Product runtime namespace | Create `app/product_runtime/` with `__init__.py`, `catalog.py`, `ownership.py` | None |
| 3 | Provider gateway | Create `app/product_runtime/ai/provider_gateway.py`; make it delegate to existing `provider_registry` | Low |
| 4 | Smart Edit -> WorkflowJob | Add `smart_edit_*` job types to `workflow_jobs.py`; create workflow handler; make sync route an enqueue adapter | Medium |
| 5 | Due Diligence -> WorkflowJob | Add `diligence_*` job types; create workflow handler; make sync route an enqueue adapter | Medium |
| 6 | Smart Deck ai_orchestration -> enqueue adapter | Convert `POST /ai/orchestrate` to create WorkflowJob + return 202 | Medium |
| 7 | Frontend: extract Smart Edit component | Move 1237-line page component into `src/lib/features/deck-product/smart-edit/` | Low |
| 8 | Frontend: extract Due Diligence component | Move 1034-line page component into `src/lib/features/deck-product/due-diligence/` | Low |
| 9 | Frontend: unified API client | Create `src/lib/features/deck-product/api/` with typed clients per domain | Low |
| 10 | Disable competing execution paths | Comment out `SmartDeckOrchestrator` direct execution; add preservation headers | Low |
| 11 | Prune dead code | Remove only code that has zero imports, zero route registrations, zero test references | Low |

---

## 11. Statement

This document was produced by reading every route file, service file, model file, worker file, API client file, and page component in both repositories. No code was modified. No files were deleted. No decisions were made on behalf of the user.

The judgment is: **the product has three execution authorities and five competing review objects. The correct consolidation is to make `workflow_jobs` the single control plane, absorb Smart Edit and Due Diligence into durable workflows, convert the sync orchestrator into an enqueue adapter, and unify the provider layer behind a single gateway.**

Every existing capability must be preserved. Every existing route must remain accessible. The migration is structural, not behavioral.
