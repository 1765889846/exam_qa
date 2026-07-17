/**
 * Vertical column splitter — drag to resize, persist px width in localStorage.
 */
export function enableColumnResize({
  root,
  cssVar,
  storageKey,
  min = 180,
  max = 480,
  defaultWidth = 260,
}) {
  if (!root) return;
  const handle = root.querySelector("[data-sz-splitter]");
  if (!handle) return;

  const clamp = (n) => Math.min(max, Math.max(min, Math.round(n)));

  let saved = Number(localStorage.getItem(storageKey));
  if (!Number.isFinite(saved)) saved = defaultWidth;
  root.style.setProperty(cssVar, `${clamp(saved)}px`);

  let dragging = false;
  let startX = 0;
  let startW = 0;

  const onMove = (e) => {
    if (!dragging) return;
    const dx = e.clientX - startX;
    const next = clamp(startW + dx);
    root.style.setProperty(cssVar, `${next}px`);
  };

  const onUp = () => {
    if (!dragging) return;
    dragging = false;
    document.body.classList.remove("sz-resizing");
    const raw = getComputedStyle(root).getPropertyValue(cssVar).trim();
    const px = Number.parseFloat(raw);
    if (Number.isFinite(px)) localStorage.setItem(storageKey, String(clamp(px)));
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", onUp);
  };

  handle.addEventListener("pointerdown", (e) => {
    if (e.button != null && e.button !== 0) return;
    e.preventDefault();
    dragging = true;
    startX = e.clientX;
    startW = Number.parseFloat(getComputedStyle(root).getPropertyValue(cssVar)) || defaultWidth;
    document.body.classList.add("sz-resizing");
    handle.setPointerCapture?.(e.pointerId);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  });

  handle.addEventListener("keydown", (e) => {
    const step = e.shiftKey ? 24 : 12;
    const cur = Number.parseFloat(getComputedStyle(root).getPropertyValue(cssVar)) || defaultWidth;
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      const next = clamp(cur - step);
      root.style.setProperty(cssVar, `${next}px`);
      localStorage.setItem(storageKey, String(next));
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      const next = clamp(cur + step);
      root.style.setProperty(cssVar, `${next}px`);
      localStorage.setItem(storageKey, String(next));
    }
  });
}
