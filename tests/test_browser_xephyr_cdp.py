from __future__ import annotations

import pytest

from triview_workspace.engines.browser_xephyr import (
    cdp_args_for_panel,
    parse_cdp_port_map,
)


def test_cdp_is_disabled_without_explicit_mapping() -> None:
    assert cdp_args_for_panel("sofia-canary-agent-sofia", source={}) == ()


def test_cdp_args_are_loopback_only_for_mapped_panel() -> None:
    source = {
        "TRIVIEW_CDP_PORTS": (
            '{"sofia-canary-agent-sofia":9221,'
            '"sofia-canary-agent-rafael":9222,'
            '"sofia-canary-agent-emily":9223}'
        )
    }
    assert cdp_args_for_panel("sofia-canary-agent-rafael", source=source) == (
        "--remote-debugging-address=127.0.0.1",
        "--remote-debugging-port=9222",
    )
    assert cdp_args_for_panel("unmapped-panel", source=source) == ()


def test_cdp_mapping_rejects_invalid_or_duplicate_ports() -> None:
    with pytest.raises(ValueError, match="TRIVIEW_CDP_PORTS"):
        parse_cdp_port_map('{"a":80}')
    with pytest.raises(ValueError, match="duplicate"):
        parse_cdp_port_map('{"a":9221,"b":9221}')
    with pytest.raises(ValueError, match="TRIVIEW_CDP_PORTS"):
        parse_cdp_port_map('[]')
