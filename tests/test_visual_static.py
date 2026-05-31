from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")


def require(fragment: str, source: str, description: str) -> None:
    if fragment not in source:
        raise AssertionError(f"missing {description}: {fragment}")


def test_dashboard_visual_layers_are_present() -> None:
    require("--surface:", HTML, "surface color token")
    require("--surface-soft:", HTML, "soft surface color token")
    require(".metric::before", HTML, "metric accent layer")
    require(".node-card::before", HTML, "node accent layer")
    require(".target-row.selected", HTML, "selected target row state")
    require("chartLineAlpha", HTML, "chart line opacity helper")
    require("ctx.globalAlpha = chartLineAlpha", HTML, "series opacity application")


def test_readme_includes_dashboard_screenshot() -> None:
    require("![kkProbe dashboard](docs/dashboard.png)", README, "dashboard screenshot markdown")
    screenshot = ROOT / "docs" / "dashboard.png"
    if not screenshot.exists():
        raise AssertionError("missing docs/dashboard.png")
    if screenshot.stat().st_size < 50_000:
        raise AssertionError("dashboard screenshot is unexpectedly small")


if __name__ == "__main__":
    test_dashboard_visual_layers_are_present()
    test_readme_includes_dashboard_screenshot()
