from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")


def require(fragment: str, description: str) -> None:
    if fragment not in HTML:
        raise AssertionError(f"missing {description}: {fragment}")


def test_timeline_range_tabs_present() -> None:
    require('id="timeRangeTabs"', "time range tab container")
    require("const TIMELINE_WINDOWS = [4, 8, 12, 24];", "time range options")
    require("timelineHours: 24,", "default 24 hour timeline state")
    require("function timelineWindow", "timeline window helper")
    require("function updateTimeRangeTabs", "tab active-state updater")
    require("function setTimelineHours", "tab click handler")
    require("data-time-range", "tab button data attribute")


if __name__ == "__main__":
    test_timeline_range_tabs_present()
