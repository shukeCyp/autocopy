from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
WORKFLOW_TEMPLATE_DIRS_ENV = "WORKFLOW_TEMPLATE_DIRS"
SRT_CONTENT_PORT_SPEC = {
    "name": "srt_content",
    "port_type": "srt_content",
    "required": True,
    "description": "ASR SRT text",
}
DEFAULT_VMF_MODEL = "dinov2_vits14"
VMF_MODEL_OPTIONS = ["dinov2_vits14", "dinov2_vitb14"]


@dataclass(frozen=True)
class WorkflowTemplate:
    id: str
    name: str
    description: str
    graph_json: str
    path: Path


def workflow_template_dirs() -> list[Path]:
    dirs = [DEFAULT_TEMPLATE_DIR]
    configured = os.environ.get(WORKFLOW_TEMPLATE_DIRS_ENV, "")
    for raw_dir in configured.split(os.pathsep):
        raw_dir = raw_dir.strip()
        if raw_dir:
            dirs.append(Path(raw_dir).expanduser())
    return dirs


def list_workflow_templates() -> dict[str, WorkflowTemplate]:
    templates: dict[str, WorkflowTemplate] = {}
    for directory in workflow_template_dirs():
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            template = _load_template_file(path)
            if template is not None:
                templates[template.id] = template
    return templates


def get_workflow_template(template_id: str) -> WorkflowTemplate | None:
    return list_workflow_templates().get(template_id)


def upgrade_workflow_graph_json(graph_json: str) -> str:
    try:
        data = json.loads(graph_json)
    except Exception:
        return graph_json

    changed = False
    for node in data.get("nodes", []):
        if node.get("type") == "SegmentASR":
            outputs = node.setdefault("outputs", {})
            if "srt_path" in outputs or "srt_content" not in outputs:
                outputs.pop("srt_path", None)
                outputs["srt_content"] = dict(SRT_CONTENT_PORT_SPEC)
                changed = True
        elif node.get("type") == "SRTRewrite":
            inputs = node.setdefault("inputs", {})
            if "srt_path" in inputs or "srt_content" not in inputs:
                inputs.pop("srt_path", None)
                inputs["srt_content"] = dict(SRT_CONTENT_PORT_SPEC)
                changed = True
        elif node.get("type") == "VideoMatchVMF":
            model_param = node.get("params", {}).get("model")
            if isinstance(model_param, dict):
                if model_param.get("default") == "auto":
                    model_param["default"] = DEFAULT_VMF_MODEL
                    changed = True
                if model_param.get("options") != VMF_MODEL_OPTIONS:
                    model_param["options"] = list(VMF_MODEL_OPTIONS)
                    changed = True

    for edge in data.get("edges", []):
        if edge.get("source_node_id") == "segment_asr" and edge.get("source_port") == "srt_path":
            edge["source_port"] = "srt_content"
            changed = True
        if edge.get("target_node_id") == "srt_rewrite" and edge.get("target_port") == "srt_path":
            edge["target_port"] = "srt_content"
            changed = True

    if not changed:
        return graph_json
    return json.dumps(data, ensure_ascii=False)


def _load_template_file(path: Path) -> WorkflowTemplate | None:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception:
        return None

    template_id = str(data.get("template_id") or path.stem).strip()
    if not template_id:
        return None

    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    return WorkflowTemplate(
        id=template_id,
        name=str(metadata.get("name") or template_id),
        description=str(metadata.get("description") or ""),
        graph_json=upgrade_workflow_graph_json(raw),
        path=path,
    )
