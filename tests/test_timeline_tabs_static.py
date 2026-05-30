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


def test_timeline_windows_are_rolling_from_current_time() -> None:
    require("function timelineWindow() {", "timeline window without server timestamp")
    require("const end = Date.now();", "current browser time as window end")
    require("start: end - hours * HOUR_MS,", "rolling lookback start")
    if "if (hours === 24)" in HTML:
        raise AssertionError("24h tab must use a rolling 24 hour lookback, not the calendar day")


def test_timeline_time_labels_avoid_overlap() -> None:
    require("function drawTimeLabels(ctx, range, pad, w, h, rectWidth)", "collision-aware time label renderer")
    require("const labelPadding = 10;", "time label spacing")
    require("priority: 2", "boundary labels have priority")
    require("placed.some", "label collision check")
    if "const startLabel =" in HTML or "const endLabel =" in HTML:
        raise AssertionError("timeline must not draw separate start/end labels that can overlap tick labels")


if __name__ == "__main__":
    test_timeline_range_tabs_present()
    test_timeline_windows_are_rolling_from_current_time()
    test_timeline_time_labels_avoid_overlap()
