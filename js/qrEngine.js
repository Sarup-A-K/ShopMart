/**
 * AR QR Camera Engine & Decoder Module
 * Handles WebRTC live video streams, QR code frame analysis, and simulated triggers.
 */

class QREngine {
  constructor() {
    this.videoElement = null;
    this.canvasElement = null;
    this.canvasContext = null;
    this.stream = null;
    this.isScanning = false;
    this.scanInterval = null;
    this.onDetectCallback = null;
    this.currentCameraFacing = "environment"; // default rear camera
  }

  init(videoEl, canvasEl, callback) {
    this.videoElement = videoEl;
    this.canvasElement = canvasEl;
    if (this.canvasElement) {
      this.canvasContext = this.canvasElement.getContext("2d", { willReadFrequently: true });
    }
    this.onDetectCallback = callback;
  }

  async startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      console.warn("WebRTC camera mediaDevices API not available in this browser environment.");
      return false;
    }

    try {
      this.stopCamera();
      
      const constraints = {
        video: {
          facingMode: this.currentCameraFacing,
          width: { ideal: 1280 },
          height: { ideal: 720 }
        },
        audio: false
      };

      this.stream = await navigator.mediaDevices.getUserMedia(constraints);
      if (this.videoElement) {
        this.videoElement.srcObject = this.stream;
        await this.videoElement.play();
        this.isScanning = true;
        this.startFrameAnalysis();
      }
      return true;
    } catch (err) {
      console.error("Camera access failed or permission denied:", err);
      return false;
    }
  }

  stopCamera() {
    this.isScanning = false;
    if (this.scanInterval) {
      cancelAnimationFrame(this.scanInterval);
      this.scanInterval = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }
    if (this.videoElement) {
      this.videoElement.srcObject = null;
    }
  }

  toggleCameraFacing() {
    this.currentCameraFacing = this.currentCameraFacing === "environment" ? "user" : "environment";
    return this.startCamera();
  }

  startFrameAnalysis() {
    const processFrame = () => {
      if (!this.isScanning) return;

      if (this.videoElement && this.videoElement.readyState === this.videoElement.HAVE_ENOUGH_DATA) {
        if (this.canvasElement && this.canvasContext) {
          this.canvasElement.width = this.videoElement.videoWidth;
          this.canvasElement.height = this.videoElement.videoHeight;
          this.canvasContext.drawImage(this.videoElement, 0, 0, this.canvasElement.width, this.canvasElement.height);

          const imageData = this.canvasContext.getImageData(0, 0, this.canvasElement.width, this.canvasElement.height);

          // Use jsQR if loaded globally
          if (window.jsQR) {
            const code = window.jsQR(imageData.data, imageData.width, imageData.height, {
              inversionAttempts: "dontInvert"
            });

            if (code && code.data) {
              if (this.onDetectCallback) {
                this.onDetectCallback(code.data, code.location);
              }
            }
          }
        }
      }

      this.scanInterval = requestAnimationFrame(processFrame);
    };

    processFrame();
  }

  // Simulated scan for quick testing or manual select
  simulateScan(qrCodeValue) {
    if (this.onDetectCallback) {
      // Return simulated center location for AR overlay targeting
      const mockLocation = {
        topLeftCorner: { x: 250, y: 150 },
        topRightCorner: { x: 450, y: 150 },
        bottomRightCorner: { x: 450, y: 350 },
        bottomLeftCorner: { x: 250, y: 350 }
      };
      this.onDetectCallback(qrCodeValue, mockLocation);
    }
  }
}

window.qrEngine = new QREngine();
