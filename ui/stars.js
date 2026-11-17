/* Статичное звёздное небо: рисуется один раз и только пересчитывается при изменении размера окна. */
(() => {
  "use strict";

  const canvas = document.getElementById("stars");
  if (!canvas) return;
  const ctx = canvas.getContext("2d", { alpha: true });
  let width = 0;
  let height = 0;
  let dpr = 1;

  function draw() {
    dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    // Небольшой фиксированный рисунок звёзд поверх CSS-градиента.
    const count = Math.max(90, Math.round((width * height) / 8500));
    for (let i = 0; i < count; i += 1) {
      const x = Math.random() * width;
      const y = Math.random() * height;
      const bright = Math.random();
      const radius = bright > 0.97 ? 1.25 + Math.random() * 0.45 : 0.25 + Math.random() * 0.7;
      const alpha = bright > 0.97 ? 0.68 : 0.16 + Math.random() * 0.34;
      ctx.beginPath();
      ctx.arc(x, y, radius, 0, Math.PI * 2);
      ctx.fillStyle = bright > 0.9
        ? `rgba(208, 216, 255, ${alpha.toFixed(2)})`
        : `rgba(245, 242, 255, ${alpha.toFixed(2)})`;
      ctx.fill();

      if (bright > 0.99) {
        ctx.beginPath();
        ctx.arc(x, y, radius * 4, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(189, 199, 255, 0.035)";
        ctx.fill();
      }
    }
  }

  window.addEventListener("resize", draw, { passive: true });
  draw();
})();
