from triview_workspace.domain import LayoutSpec, NormalizedRect
from triview_workspace.engines import LayoutEngine


def test_layout_uses_normalized_percentages() -> None:
    layout = LayoutSpec(
        id="half",
        name="Half",
        slots=(NormalizedRect(0.25, 0.10, 0.50, 0.80),),
    )

    bounds = LayoutEngine().calculate(layout, 1000, 500)

    assert bounds[0].x == 250
    assert bounds[0].y == 50
    assert bounds[0].width == 500
    assert bounds[0].height == 400


def test_layout_preserves_optional_aspect_ratio() -> None:
    layout = LayoutSpec(
        id="mobile",
        name="Mobile",
        slots=(NormalizedRect(0, 0, 1, 1, aspect_ratio=0.5),),
    )

    bounds = LayoutEngine().calculate(layout, 1000, 500)

    assert bounds[0].width == 250
    assert bounds[0].height == 500
    assert bounds[0].x == 375
