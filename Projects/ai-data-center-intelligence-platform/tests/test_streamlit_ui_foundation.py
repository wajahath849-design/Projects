import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_entry_uses_modern_navigation_and_all_required_pages() -> None:
    source = (ROOT / "app/streamlit_app.py").read_text(encoding="utf-8")
    assert "st.navigation" in source
    for page in (
        "copilot.py", "live_ops.py", "simulation_lab.py", "investigation.py",
        "sustainability.py", "impact.py",
    ):
        assert page in source
        assert (ROOT / "app/app_pages" / page).exists()


def test_streamlit_sources_parse_and_avoid_deprecated_or_reasoning_ui() -> None:
    paths = [
        ROOT / "app/streamlit_app.py",
        ROOT / "app/ui_shared.py",
        *(ROOT / "app/app_pages").glob("*.py"),
    ]
    for path in paths:
        source = path.read_text(encoding="utf-8")
        ast.parse(source)
        assert "use_container_width" not in source
        assert "unsafe_allow_html" not in source
        assert "chain of thought" not in source.lower()
        assert "reasoning trace" not in source.lower()


def test_theme_and_live_fragment_are_configured() -> None:
    theme = (ROOT / ".streamlit/config.toml").read_text(encoding="utf-8")
    live = (ROOT / "app/app_pages/live_ops.py").read_text(encoding="utf-8")
    assert "[theme.light]" in theme and "[theme.dark]" in theme
    assert '@st.fragment(run_every="5s")' in live
    assert "st.metric" in live and "st.dataframe" in live
