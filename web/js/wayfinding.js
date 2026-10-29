/**
 * In-store wayfinding: route from the shopper's checkpoint (Entrance or an aisle)
 * along the front corridor and up the aisle walkway, with step-by-step directions.
 * Map canvas coordinates are 500x280 px; product coordinates are in metres (x 0-40, z 0-30).
 */
const Wayfinding = (() => {
  const MAP = { startX: 60, startY: 50, gapX: 65, aisleWidth: 45, aisleHeight: 160, numAisles: 6, corridorY: 235 };
  const STORE_DEPTH_M = 30;
  const STORE_WIDTH_M = 40;
  const M_PER_PX_X = STORE_WIDTH_M / (MAP.numAisles * MAP.gapX);
  const M_PER_PX_Y = STORE_DEPTH_M / MAP.aisleHeight;

  // Walkway runs just left of each aisle block
  const walkwayX = (aisleIdx) => MAP.startX + aisleIdx * MAP.gapX - 10;

  function checkpointCoords(checkpoint) {
    if (checkpoint && checkpoint.startsWith("aisle-")) {
      const n = parseInt(checkpoint.split("-")[1], 10);
      return { x: walkwayX(n - 1), y: MAP.corridorY, label: `Aisle ${n}` };
    }
    return { x: 30, y: 260, label: "Entrance" };
  }

  function productTarget(product) {
    const loc = product && product.location;
    if (!loc || !loc.coordinates) return null;
    const aisleNum = parseInt(String(loc.aisle).replace(/\D/g, ""), 10) || 1;
    return {
      aisleIdx: aisleNum - 1,
      x: MAP.startX + (loc.coordinates.x / STORE_WIDTH_M) * (MAP.numAisles * MAP.gapX),
      y: MAP.startY + (loc.coordinates.z / STORE_DEPTH_M) * MAP.aisleHeight,
      z: loc.coordinates.z
    };
  }

  function computeRoute(product, start) {
    const target = productTarget(product);
    if (!target) return null;
    const wx = walkwayX(target.aisleIdx);
    const raw = [
      { x: start.x, y: start.y },
      { x: start.x, y: MAP.corridorY },
      { x: wx, y: MAP.corridorY },
      { x: wx, y: target.y },
      { x: target.x, y: target.y }
    ];
    const points = raw.filter((p, i) => i === 0 || Math.abs(p.x - raw[i - 1].x) + Math.abs(p.y - raw[i - 1].y) > 1);
    let meters = 0;
    for (let i = 1; i < points.length; i++) {
      meters += Math.abs(points[i].x - points[i - 1].x) * M_PER_PX_X + Math.abs(points[i].y - points[i - 1].y) * M_PER_PX_Y;
    }

    const loc = product.location;
    const aisleName = `Aisle ${target.aisleIdx + 1}`;
    const steps = [];
    const corridorM = Math.round(Math.abs(wx - start.x) * M_PER_PX_X);
    if (start.label === "Entrance") {
      steps.push(`From the Entrance, walk ${corridorM} m right along the front corridor to ${aisleName}.`);
    } else if (corridorM > 0) {
      steps.push(`From ${start.label}, walk ${corridorM} m ${wx > start.x ? "right" : "left"} along the front corridor to ${aisleName}.`);
    } else {
      steps.push(`You're already at the front of ${aisleName}.`);
    }
    const depth = target.z < 8 ? "front" : target.z < 18 ? "middle" : "back";
    const aisleM = Math.round((MAP.corridorY - target.y) * M_PER_PX_Y);
    steps.push(`Turn into ${aisleName} and walk ${aisleM} m to the ${depth} of the aisle.`);
    steps.push(`${loc.section} shelf is on your right; look for ${product.brand}.`);

    return { points, steps, meters: Math.round(meters), aisleName, target };
  }

  function drawMap(canvas, product, start, route) {
    const ctx = canvas.getContext("2d");
    const { width: w, height: h } = canvas;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#f7f9fb";
    ctx.fillRect(0, 0, w, h);

    // Front corridor
    ctx.fillStyle = "#e9eef3";
    ctx.fillRect(0, MAP.corridorY - 14, w, 28);
    ctx.fillStyle = "#7b8794";
    ctx.font = "10px Inter, sans-serif";
    ctx.textAlign = "right";
    ctx.fillText("Front corridor", w - 10, MAP.corridorY + 4);

    for (let i = 0; i < MAP.numAisles; i++) {
      const ax = MAP.startX + i * MAP.gapX;
      const isTarget = route && route.target.aisleIdx === i;
      ctx.fillStyle = isTarget ? "#dff1ec" : "#ffffff";
      ctx.strokeStyle = isTarget ? "#0b8a6f" : "#c3cbd4";
      ctx.lineWidth = isTarget ? 2 : 1;
      ctx.fillRect(ax, MAP.startY, MAP.aisleWidth, MAP.aisleHeight);
      ctx.strokeRect(ax, MAP.startY, MAP.aisleWidth, MAP.aisleHeight);
      ctx.fillStyle = isTarget ? "#076b56" : "#56616e";
      ctx.font = `${isTarget ? "bold " : ""}13px Inter, sans-serif`;
      ctx.textAlign = "center";
      ctx.save();
      ctx.translate(ax + MAP.aisleWidth / 2, MAP.startY + MAP.aisleHeight / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText(`Aisle ${i + 1}`, 0, 4);
      ctx.restore();
    }

    if (route) {
      ctx.beginPath();
      ctx.setLineDash([6, 5]);
      route.points.forEach((pt, i) => (i === 0 ? ctx.moveTo(pt.x, pt.y) : ctx.lineTo(pt.x, pt.y)));
      ctx.strokeStyle = "#0b8a6f";
      ctx.lineWidth = 3;
      ctx.stroke();
      ctx.setLineDash([]);

      route.points.slice(1, -1).forEach((pt, i) => {
        ctx.beginPath();
        ctx.arc(pt.x, pt.y, 8, 0, 2 * Math.PI);
        ctx.fillStyle = "#ffffff";
        ctx.fill();
        ctx.strokeStyle = "#0b8a6f";
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.fillStyle = "#076b56";
        ctx.font = "bold 10px Inter, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(String(i + 1), pt.x, pt.y + 3.5);
      });

      const { x: tx, y: ty } = route.target;
      ctx.beginPath();
      ctx.arc(tx, ty, 9, 0, 2 * Math.PI);
      ctx.fillStyle = "#c7254e";
      ctx.fill();
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = "#0f1720";
      ctx.font = "bold 13px Inter, sans-serif";
      ctx.textAlign = "left";
      ctx.fillText(product.brand || "Item", tx + 12, ty + 4);
    }

    // Shopper
    ctx.beginPath();
    ctx.arc(start.x, start.y, 8, 0, 2 * Math.PI);
    ctx.fillStyle = "#0a6ebd";
    ctx.fill();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.fillStyle = "#0f1720";
    ctx.font = "bold 13px Inter, sans-serif";
    ctx.textAlign = "left";
    ctx.fillText(`You (${start.label})`, start.x + 12, Math.min(start.y + 4, h - 6));
  }

  /** Wire a wayfinding panel: checkpoint <select>, steps <ol>, summary text and map <canvas>. */
  function init({ product, canvas, select, stepsEl, summaryEl }) {
    function update() {
      const start = checkpointCoords(select.value);
      const route = computeRoute(product, start);
      stepsEl.innerHTML = "";
      if (route) {
        summaryEl.textContent = `About ${route.meters} m from ${start.label}`;
        route.steps.forEach(st => {
          const li = document.createElement("li");
          li.textContent = st;
          stepsEl.appendChild(li);
        });
      } else {
        summaryEl.textContent = (product.location && product.location.guidance) || "";
      }
      drawMap(canvas, product, start, route);
    }
    select.addEventListener("change", update);
    update();
  }

  /** Walking distance in metres from a checkpoint ('entrance' or 'aisle-N') to a product, or null. */
  function distance(product, checkpoint) {
    const route = computeRoute(product, checkpointCoords(checkpoint));
    return route ? route.meters : null;
  }

  return { init, distance };
})();
