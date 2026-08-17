from __future__ import annotations

from pathlib import Path

from triview_workspace.mcf_binding import McfWorkspaceBinding
from triview_workspace.mcf_cockpit import (
    McfCockpitContext,
    bind_workspace_context,
    binding_action_label,
    unbind_workspace_context,
)


def test_bind_workspace_context_passes_only_non_secret_reference_fields(tmp_path: Path) -> None:
    calls: list[tuple[object, ...]] = []
    returned = McfWorkspaceBinding(
        workspace_id="workspace-a",
        project_root=tmp_path,
        project_id="project-a",
        mission_id="mission-1",
        runtime_url="https://mcf.example.test/",
    )

    class FakeBinder:
        def bind(
            self,
            workspace_id: str,
            project_root: Path,
            *,
            mission_id: str | None = None,
            runtime_url: str | None = None,
        ) -> McfWorkspaceBinding:
            calls.append((workspace_id, project_root, mission_id, runtime_url))
            return returned

    context = McfCockpitContext(
        project_root=tmp_path,
        mission_id="mission-1",
        runtime_url="https://mcf.example.test/",
        workspace_id="workspace-a",
        binding_persisted=False,
        _session_token="must-never-reach-binder",
    )

    result = bind_workspace_context(context, FakeBinder())  # type: ignore[arg-type]

    assert result == returned
    assert calls == [
        (
            "workspace-a",
            tmp_path.resolve(),
            "mission-1",
            "https://mcf.example.test/",
        )
    ]
    assert "must-never-reach-binder" not in repr(calls)


def test_unbind_workspace_context_removes_only_workspace_reference(tmp_path: Path) -> None:
    calls: list[str] = []

    class FakeBinder:
        def unbind(self, workspace_id: str) -> bool:
            calls.append(workspace_id)
            return True

    context = McfCockpitContext(
        project_root=tmp_path,
        workspace_id="workspace-a",
        binding_persisted=True,
        _session_token="secret",
    )

    assert unbind_workspace_context(context, FakeBinder()) is True  # type: ignore[arg-type]
    assert calls == ["workspace-a"]
    assert "secret" not in repr(calls)


def test_binding_action_label_reflects_persisted_reference_state(tmp_path: Path) -> None:
    unbound = McfCockpitContext(
        project_root=tmp_path,
        workspace_id="workspace-a",
        binding_persisted=False,
    )
    bound = McfCockpitContext(
        project_root=tmp_path,
        workspace_id="workspace-a",
        binding_persisted=True,
    )
    standalone = McfCockpitContext(project_root=tmp_path)

    assert binding_action_label(unbound) == "Vincular workspace"
    assert binding_action_label(bound) == "Desvincular workspace"
    assert binding_action_label(standalone) is None
