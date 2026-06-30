# Schema-Driven Node Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make node definitions schema-driven, add rule-based node validation, and expose explicit executing-node events for reliable frontend highlighting.

**Architecture:** Backend registered node classes become the source of truth for node schemas. `Node` gains validation hooks that return structured issues, and `Executor` validates before running each node while emitting `node_executing` events. The frontend loads node schemas from `/api/nodes`, keeps `executingNodeId` separate from status, and renders validation issues on nodes and in the detail panel.

**Tech Stack:** FastAPI, Python dataclasses, existing pipeline `Node`/`Executor`, React + Zustand + ReactFlow, pytest, Vite build.

---

### Task 1: Structured Validation Model

**Files:**
- Modify: `app/pipeline/types.py`
- Modify: `app/pipeline/node.py`
- Test: `tests/test_pipeline/test_node.py`

- [ ] Add `ValidationIssue` with `level`, `code`, `message`, `field`, and `node_id`.
- [ ] Add default `Node.validate()` that checks required connected inputs and required params.
- [ ] Add `Node.schema()` as a serializable runtime schema.
- [ ] Test that missing required params return `ValidationIssue(level="error", code="missing_param")`.

### Task 2: Node-Specific Rules

**Files:**
- Modify: `app/nodes/video_input.py`
- Modify: `app/nodes/tts_extract.py`
- Modify: `app/nodes/voice_vad.py`
- Modify: `app/nodes/segment_asr.py`
- Modify: `app/nodes/srt_rewrite.py`
- Modify: `app/nodes/tts_generate.py`
- Test: `tests/test_nodes/test_nodes.py`

- [ ] Mark truly required fields in `ParamSpec`: video `path`, API keys, Minimax IDs, model names.
- [ ] Add model-file validation through `resolve_model_path`.
- [ ] Add API key validation with environment fallback for Gemini/Yunwu nodes.
- [ ] Test missing model, missing path, and missing API credential cases.

### Task 3: Executor Validation And Executing Events

**Files:**
- Modify: `app/pipeline/executor.py`
- Modify: `app/pipeline/types.py`
- Test: `tests/test_pipeline/test_executor.py`

- [ ] Add `ExecutorEvent.node_executing(node_id)`.
- [ ] Emit `node_executing` before cache checks and before actual execution.
- [ ] Run node validation after inputs and params are resolved.
- [ ] Fail a node with structured validation errors before calling `node.execute`.
- [ ] Include validation issues in `NodeResult.to_dict()`.

### Task 4: Backend Node Schema API

**Files:**
- Create: `app/server/routes/nodes.py`
- Modify: `app/server/main.py`
- Test: `tests/test_server/test_api.py`

- [ ] Add `GET /api/nodes` returning all registered node schemas.
- [ ] Add `GET /api/nodes/{node_type}` returning one schema.
- [ ] Test that `SegmentASR` includes `timing_offset_ms` and validation metadata.

### Task 5: Frontend Uses Backend Schemas

**Files:**
- Modify: `frontend/src/nodeSpecs.ts`
- Modify: `frontend/src/components/Canvas.tsx`
- Modify: `frontend/src/types.ts`

- [ ] Replace hard-coded fallback node specs with backend schema loading.
- [ ] Keep local fallback only for startup failure.
- [ ] Preserve template-loaded node params and user `paramValues`.

### Task 6: Frontend Executing Highlight And Issues

**Files:**
- Modify: `frontend/src/stores/useStore.ts`
- Modify: `frontend/src/components/TopBar.tsx`
- Modify: `frontend/src/components/custom/PipelineNode.tsx`
- Modify: `frontend/src/components/NodeDetail.tsx`
- Modify: `frontend/src/index.css`

- [ ] Add `executingNodeId` and `validationIssues` to the store/node types.
- [ ] Handle websocket `node_executing` by setting `executingNodeId`, selecting the node, and rendering a ComfyUI-style active glow.
- [ ] Show validation error/warning badges on nodes.
- [ ] Show issue details in the node detail panel.

### Task 7: Verification

**Files:**
- Test command targets only.

- [ ] Run `uv run pytest -q`.
- [ ] Run `npm run build` in `frontend/`.
- [ ] Start backend on an unused port and verify `/api/health` and `/api/nodes`.
- [ ] Run a workflow with a deliberately missing model and confirm the failing node is highlighted with a validation issue.
