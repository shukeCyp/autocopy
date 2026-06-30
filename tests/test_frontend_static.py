from pathlib import Path


def test_running_workflow_does_not_take_over_canvas_viewport_or_selection():
    canvas = Path("frontend/src/components/Canvas.tsx").read_text()
    topbar = Path("frontend/src/components/TopBar.tsx").read_text()

    assert ".setCenter(" not in canvas
    assert "setSelectedNodeId(event.node_id)" not in topbar
    assert "setSelectedNodeId(task.current_node_id)" not in topbar


def test_last_node_is_not_rendered_as_executing_after_workflow_finishes():
    canvas = Path("frontend/src/components/Canvas.tsx").read_text()

    assert "executing: running && executingNodeId === n.id" in canvas


def test_canvas_viewport_is_not_auto_fit_or_bounded():
    canvas = Path("frontend/src/components/Canvas.tsx").read_text()

    assert "fitView" not in canvas
    assert "translateExtent" not in canvas
    assert "nodeExtent" not in canvas
    assert "panOnDrag" in canvas
    assert "zoomOnScroll" in canvas


def test_default_templates_are_saved_in_place_instead_of_copied():
    topbar = Path("frontend/src/components/TopBar.tsx").read_text()

    assert "activeTemplateBuiltin ? `${name} Copy`" not in topbar


def test_draft_folder_uses_directory_picker():
    pipeline_node = Path("frontend/src/components/custom/PipelineNode.tsx").read_text()
    node_detail = Path("frontend/src/components/NodeDetail.tsx").read_text()

    assert "/files/select-directory" in pipeline_node
    assert "name === 'draft_folder'" in pipeline_node
    assert "/files/select-directory" in node_detail
    assert "name === 'draft_folder'" in node_detail
