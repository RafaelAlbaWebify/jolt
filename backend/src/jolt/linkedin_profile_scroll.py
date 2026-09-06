from __future__ import annotations

from typing import Any


_PROFILE_SCROLL_SURFACE_SCRIPT = r"""
() => {
  const isScrollable = (element) => {
    if (!(element instanceof HTMLElement)) return false;
    const style = window.getComputedStyle(element);
    const overflowY = style.overflowY;
    return (
      (overflowY === "auto" || overflowY === "scroll" || overflowY === "overlay") &&
      element.scrollHeight > element.clientHeight + 2
    );
  };

  const candidates = Array.from(document.querySelectorAll("main, [role='main'], div, section"))
    .filter((element) => isScrollable(element));

  const scored = candidates
    .map((element) => {
      const rect = element.getBoundingClientRect();
      const visibleHeight = Math.max(
        0,
        Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0)
      );
      const textLength = (element.innerText || "").trim().length;
      const scrollRange = Math.max(element.scrollHeight - element.clientHeight, 0);
      return { element, visibleHeight, textLength, scrollRange };
    })
    .filter((item) => item.visibleHeight > 0 && item.scrollRange > 2)
    .sort((a, b) => {
      if (b.textLength !== a.textLength) return b.textLength - a.textLength;
      if (b.visibleHeight !== a.visibleHeight) return b.visibleHeight - a.visibleHeight;
      return b.scrollRange - a.scrollRange;
    });

  const container = scored.length ? scored[0].element : null;
  if (container) {
    container.scrollTop = 0;
    return {
      strategy: "scrollable_container",
      position: container.scrollTop,
      viewport_extent: container.clientHeight,
      scroll_extent: container.scrollHeight,
      can_scroll: container.scrollHeight > container.clientHeight + 2,
    };
  }

  window.scrollTo({ top: 0, behavior: "instant" });
  const documentExtent = Math.max(
    document.body?.scrollHeight || 0,
    document.documentElement?.scrollHeight || 0
  );
  return {
    strategy: "window",
    position: window.scrollY,
    viewport_extent: window.innerHeight,
    scroll_extent: documentExtent,
    can_scroll: documentExtent > window.innerHeight + 2,
  };
}
"""

_PROFILE_SCROLL_ADVANCE_SCRIPT = r"""
() => {
  const isScrollable = (element) => {
    if (!(element instanceof HTMLElement)) return false;
    const style = window.getComputedStyle(element);
    const overflowY = style.overflowY;
    return (
      (overflowY === "auto" || overflowY === "scroll" || overflowY === "overlay") &&
      element.scrollHeight > element.clientHeight + 2
    );
  };

  const candidates = Array.from(document.querySelectorAll("main, [role='main'], div, section"))
    .filter((element) => isScrollable(element));

  const scored = candidates
    .map((element) => {
      const rect = element.getBoundingClientRect();
      const visibleHeight = Math.max(
        0,
        Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0)
      );
      const textLength = (element.innerText || "").trim().length;
      const scrollRange = Math.max(element.scrollHeight - element.clientHeight, 0);
      return { element, visibleHeight, textLength, scrollRange };
    })
    .filter((item) => item.visibleHeight > 0 && item.scrollRange > 2)
    .sort((a, b) => {
      if (b.textLength !== a.textLength) return b.textLength - a.textLength;
      if (b.visibleHeight !== a.visibleHeight) return b.visibleHeight - a.visibleHeight;
      return b.scrollRange - a.scrollRange;
    });

  const container = scored.length ? scored[0].element : null;
  if (container) {
    const before = container.scrollTop;
    const extent = container.scrollHeight;
    const viewport = Math.max(container.clientHeight, 1);
    const maxTop = Math.max(extent - viewport, 0);
    const step = Math.max(Math.floor(viewport * 0.75), 220);
    container.scrollTop = Math.min(before + step, maxTop);
    return {
      strategy: "scrollable_container",
      before,
      after: container.scrollTop,
      viewport_extent: viewport,
      scroll_extent: extent,
      at_end: container.scrollTop + viewport >= extent - 4,
    };
  }

  const before = window.scrollY;
  const extent = Math.max(
    document.body?.scrollHeight || 0,
    document.documentElement?.scrollHeight || 0
  );
  const viewport = Math.max(window.innerHeight, 1);
  const maxTop = Math.max(extent - viewport, 0);
  const step = Math.max(Math.floor(viewport * 0.75), 300);
  const target = Math.min(before + step, maxTop);
  window.scrollTo({ top: target, behavior: "instant" });
  return {
    strategy: "window",
    before,
    after: window.scrollY,
    viewport_extent: viewport,
    scroll_extent: extent,
    at_end: window.scrollY + viewport >= extent - 4,
  };
}
"""


def reset_profile_scroll_surface(page: Any) -> dict[str, object]:
    result = page.evaluate(_PROFILE_SCROLL_SURFACE_SCRIPT)
    return result if isinstance(result, dict) else {"strategy": "unknown"}


def advance_profile_scroll_surface(page: Any) -> dict[str, object]:
    result = page.evaluate(_PROFILE_SCROLL_ADVANCE_SCRIPT)
    return result if isinstance(result, dict) else {"strategy": "unknown"}
