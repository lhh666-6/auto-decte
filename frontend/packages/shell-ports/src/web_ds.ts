/**
 * Web (browser) implementation of Shell Ports.
 *
 * Uses standard Web APIs:
 *   - File Port   → <input type="file"> / FileReader
 *   - Camera Port → MediaDevices.getUserMedia + <canvas> capture
 *   - Scanner Port→ not available in browser (throws)
 *   - Audio Port  → MediaRecorder API
 *   - Notification→ Notification API
 *
 * @packageDocumentation
 */

import type {
  FilePort,
  FileHandle,
  FileOpenOptions,
  CameraPort,
  CameraCapture,
  ScannerPort,
  AudioPort,
  AudioRecording,
  NotificationPort,
  NotificationOptions,
} from "./ports_ds.js";

// ─── Web File Port ───────────────────────────────────────────────────────────

function createFileHandle(file: File): FileHandle {
  return {
    name: file.name,
    size: file.size,
    mimeType: file.type,
    read: () =>
      new Promise<Uint8Array>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
          const result = reader.result as ArrayBuffer;
          resolve(new Uint8Array(result));
        };
        reader.onerror = () => reject(reader.error);
        reader.readAsArrayBuffer(file);
      }),
  };
}

export class WebFilePort implements FilePort {
  async open(options?: FileOpenOptions): Promise<FileHandle[]> {
    return new Promise((resolve, reject) => {
      const input = document.createElement("input");
      input.type = "file";
      if (options?.multiple) input.multiple = true;
      if (options?.filters) {
        // Build accept attribute from filters
        input.accept = options.filters
          .flatMap((f) => f.extensions)
          .join(",");
      }

      input.onchange = () => {
        const files = input.files;
        if (!files || files.length === 0) {
          reject(new Error("No files selected"));
          return;
        }
        resolve(Array.from(files).map(createFileHandle));
      };

      input.onerror = () => reject(new Error("File picker failed"));
      input.click();
    });
  }

  async read(handle: FileHandle): Promise<Uint8Array> {
    return handle.read();
  }
}

// ─── Web Camera Port ─────────────────────────────────────────────────────────

export class WebCameraPort implements CameraPort {
  private stream: MediaStream | null = null;
  private video: HTMLVideoElement | null = null;

  async initialize(): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment" },
      audio: false,
    });

    this.video = document.createElement("video");
    this.video.srcObject = this.stream;
    this.video.play();
  }

  async capture(): Promise<CameraCapture> {
    if (!this.video || !this.stream) {
      throw new Error("Camera not initialized. Call initialize() first.");
    }

    const width = this.video.videoWidth || 640;
    const height = this.video.videoHeight || 480;

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Failed to get canvas 2D context");

    ctx.drawImage(this.video, 0, 0, width, height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.92);

    return { dataUrl, width, height };
  }

  async release(): Promise<void> {
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
    this.video = null;
  }
}

// ─── Web Scanner Port (stub) ─────────────────────────────────────────────────

export class WebScannerPort implements ScannerPort {
  async listDevices(): Promise<string[]> {
    // Browser has no native scanner API
    return [];
  }

  async scan(): Promise<Uint8Array> {
    throw new Error(
      "Scanner is not available in browser context. Use the desktop build."
    );
  }
}

// ─── Web Audio Port ──────────────────────────────────────────────────────────

export class WebAudioPort implements AudioPort {
  private mediaRecorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private startTime = 0;

  async startRecording(options?: { deviceId?: string }): Promise<void> {
    this.chunks = [];

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: options?.deviceId
        ? { deviceId: { exact: options.deviceId } }
        : true,
    });

    this.mediaRecorder = new MediaRecorder(stream, {
      mimeType: MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "audio/mp4",
    });

    this.mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) this.chunks.push(e.data);
    };

    this.startTime = Date.now();
    this.mediaRecorder.start();
  }

  async stopRecording(): Promise<AudioRecording> {
    return new Promise((resolve, reject) => {
      if (!this.mediaRecorder) {
        reject(new Error("No active recording"));
        return;
      }

      this.mediaRecorder.onstop = () => {
        const blob = new Blob(this.chunks, {
          type: this.mediaRecorder?.mimeType || "audio/webm",
        });
        this.mediaRecorder?.stream.getTracks().forEach((t) => t.stop());
        resolve({
          blob,
          durationMs: Date.now() - this.startTime,
        });
      };

      this.mediaRecorder.stop();
    });
  }

  async play(blob: Blob): Promise<void> {
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    return new Promise((resolve, reject) => {
      audio.onended = () => {
        URL.revokeObjectURL(url);
        resolve();
      };
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error("Audio playback failed"));
      };
      audio.play();
    });
  }
}

// ─── Web Notification Port ───────────────────────────────────────────────────

export class WebNotificationPort implements NotificationPort {
  private permission: NotificationPermission | null = null;

  private async ensurePermission(): Promise<boolean> {
    if (!("Notification" in window)) return false;

    if (Notification.permission === "granted") {
      this.permission = "granted";
      return true;
    }

    if (Notification.permission === "denied") return false;

    const result = await Notification.requestPermission();
    this.permission = result;
    return result === "granted";
  }

  async notify(options: NotificationOptions): Promise<boolean> {
    const allowed = await this.ensurePermission();
    if (!allowed) return false;

    const notif = new Notification(options.title, {
      body: options.body,
      tag: `form-detection-${Date.now()}`,
    });

    return new Promise((resolve) => {
      notif.onclick = () => {
        notif.close();
        resolve(true);
      };
      if (options.timeoutMs && options.timeoutMs > 0) {
        setTimeout(() => {
          notif.close();
          resolve(false);
        }, options.timeoutMs);
      }
    });
  }
}
