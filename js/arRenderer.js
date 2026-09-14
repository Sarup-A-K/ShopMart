/**
 * 3D AR Spatial Overlay & Store Wayfinder Radar Engine
 * Manages holographic target locks, 3D card perspective tilt, and real-time indoor radar HUD.
 */

class ARRenderer {
  constructor() {
    this.audioCtx = null;
    this.userHeading = 0; // simulated compass heading 0-360
    this.userPos = { x: 0, y: 0, z: 0 }; // user starting location (Entrance)
  }

  // Play futuristic AR lock-on audio chime using Web Audio API synth
  playLockChime() {
    try {
      if (!this.audioCtx) {
        this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (this.audioCtx.state === 'suspended') {
        this.audioCtx.resume();
      }
      const osc = this.audioCtx.createOscillator();
      const gain = this.audioCtx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(587.33, this.audioCtx.currentTime); // D5 note
      osc.frequency.exponentialRampToValueAtTime(880.00, this.audioCtx.currentTime + 0.08); // A5 note

      gain.gain.setValueAtTime(0.15, this.audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, this.audioCtx.currentTime + 0.2);

      osc.connect(gain);
      gain.connect(this.audioCtx.destination);

      osc.start();
      osc.stop(this.audioCtx.currentTime + 0.22);
    } catch (e) {
      // Audio fallback silent
    }
  }

  // Calculate distance in meters between user position and product 3D store coordinates
  calculateDistance(targetCoords) {
    if (!targetCoords) return 0;
    const dx = targetCoords.x - this.userPos.x;
    const dz = targetCoords.z - this.userPos.z;
    return Math.round(Math.sqrt(dx * dx + dz * dz));
  }

  // Calculate relative angle/bearing to product location (0 to 360 degrees)
  calculateBearing(targetCoords) {
    if (!targetCoords) return 0;
    const dx = targetCoords.x - this.userPos.x;
    const dz = targetCoords.z - this.userPos.z;
    let angle = Math.atan2(dx, dz) * (180 / Math.PI);
    if (angle < 0) angle += 360;
    return Math.round(angle);
  }

  // Render 3D spatial perspective tilt on AR Card when user moves mouse / touches screen
  applyCardTilt(cardElement, event) {
    if (!cardElement) return;
    const rect = cardElement.getBoundingClientRect();
    const x = event.clientX - rect.left - rect.width / 2;
    const y = event.clientY - rect.top - rect.height / 2;

    const tiltX = (y / (rect.height / 2)) * -12;
    const tiltY = (x / (rect.width / 2)) * 12;

    cardElement.style.transform = `perspective(1000px) rotateX(${tiltX}deg) rotateY(${tiltY}deg) scale3d(1.02, 1.02, 1.02)`;
  }

  resetCardTilt(cardElement) {
    if (!cardElement) return;
    cardElement.style.transform = `perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)`;
  }

  // Update dynamic store radar compass visual canvas
  drawRadarHUD(canvas, targetCoords, themeColor = "#10b981") {
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = width / 2 - 8;

    ctx.clearRect(0, 0, width, height);

    // Draw background outer circle
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
    ctx.fillStyle = "rgba(15, 23, 42, 0.75)";
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "rgba(255, 255, 255, 0.15)";
    ctx.stroke();

    // Draw concentric radar rings
    [0.3, 0.65, 0.95].forEach(r => {
      ctx.beginPath();
      ctx.arc(centerX, centerY, radius * r, 0, 2 * Math.PI);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
      ctx.lineWidth = 1;
      ctx.stroke();
    });

    // Draw crosshair axes
    ctx.beginPath();
    ctx.moveTo(centerX, centerY - radius);
    ctx.lineTo(centerX, centerY + radius);
    ctx.moveTo(centerX - radius, centerY);
    ctx.lineTo(centerX + radius, centerY);
    ctx.strokeStyle = "rgba(255, 255, 255, 0.1)";
    ctx.stroke();

    // Center user position blip
    ctx.beginPath();
    ctx.arc(centerX, centerY, 5, 0, 2 * Math.PI);
    ctx.fillStyle = "#38bdf8"; // User blue dot
    ctx.fill();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Calculate target blip on radar
    const distance = this.calculateDistance(targetCoords);
    const bearing = this.calculateBearing(targetCoords);

    // Scale distance (max radar range 50m)
    const normalizedDist = Math.min(distance / 50, 0.85) * radius;
    const angleRad = (bearing - 90) * (Math.PI / 180);

    const targetX = centerX + normalizedDist * Math.cos(angleRad);
    const targetY = centerY + normalizedDist * Math.sin(angleRad);

    // Draw line to target
    ctx.beginPath();
    ctx.setLineDash([3, 3]);
    ctx.moveTo(centerX, centerY);
    ctx.lineTo(targetX, targetY);
    ctx.strokeStyle = themeColor;
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw target blip pulse
    ctx.beginPath();
    ctx.arc(targetX, targetY, 7, 0, 2 * Math.PI);
    ctx.fillStyle = themeColor;
    ctx.fill();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.stroke();
  }
}

window.arRenderer = new ARRenderer();
