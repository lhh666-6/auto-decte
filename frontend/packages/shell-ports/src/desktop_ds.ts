/**
 * Desktop (Tauri) implementation of Shell Ports — STUBS ONLY.
 *
 * These stubs define the shape but do NOT import @tauri-apps/* packages.
 * When ready, replace each stub body with the real Tauri API call:
 *
 *   - File Port   → @tauri-apps/plugin-dialog (open) + @tauri-apps/plugin-fs (read)
 *   - Camera Port → @tauri-apps/plugin-camera or IPC to Rust backend
 *   - Scanner Port→ IPC to Rust backend (e.g. SANE bindings)
 *   - Audio Port  → @tauri-apps/plugin-media or IPC to Rust backend
 *   - Notification→ @tauri-apps/plugin-notification
 *
 * To activate, install the dependency and replace the stub bodies.
 *   npm install @tauri-apps/api @tauri-apps/plugin-dialog @tauri-apps/plugin-fs @tauri-apps/plugin-notification
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
  ScannerOptions,
  AudioPort,
  AudioRecording,
  NotificationPort,
  NotificationOptions,
} from "./ports_ds.js";

// ─── Desktop File Port — STUB ────────────────────────────────────────────────

export class DesktopFilePort implements FilePort {
  async open(_options?: FileOpenOptions): Promise<FileHandle[]> {
    // TODO: Replace with @tauri-apps/plugin-dialog open()
    throw new Error("DesktopFilePort not implemented — add @tauri-apps/plugin-dialog");
  }

  async read(_handle: FileHandle): Promise<Uint8Array> {
    // TODO: Replace with @tauri-apps/plugin-fs readFile()
    throw new Error("DesktopFilePort.read not implemented — add @tauri-apps/plugin-fs");
  }
}

// ─── Desktop Camera Port — STUB ──────────────────────────────────────────────

export class DesktopCameraPort implements CameraPort {
  async initialize(): Promise<void> {
    throw new Error("DesktopCameraPort not implemented — use IPC or @tauri-apps/plugin-camera");
  }

  async capture(): Promise<CameraCapture> {
    throw new Error("DesktopCameraPort.capture not implemented");
  }

  async release(): Promise<void> {
    // no-op stub
  }
}

// ─── Desktop Scanner Port — STUB ─────────────────────────────────────────────

export class DesktopScannerPort implements ScannerPort {
  async listDevices(): Promise<string[]> {
    throw new Error("DesktopScannerPort not implemented — delegate to Rust/SANE backend");
  }

  async scan(_options?: ScannerOptions): Promise<Uint8Array> {
    throw new Error("DesktopScannerPort.scan not implemented");
  }
}

// ─── Desktop Audio Port — STUB ───────────────────────────────────────────────

export class DesktopAudioPort implements AudioPort {
  async startRecording(): Promise<void> {
    throw new Error("DesktopAudioPort not implemented — use IPC or @tauri-apps/plugin-media");
  }

  async stopRecording(): Promise<AudioRecording> {
    throw new Error("DesktopAudioPort.stopRecording not implemented");
  }

  async play(_blob: Blob): Promise<void> {
    throw new Error("DesktopAudioPort.play not implemented");
  }
}

// ─── Desktop Notification Port — STUB ────────────────────────────────────────

export class DesktopNotificationPort implements NotificationPort {
  async notify(_options: NotificationOptions): Promise<boolean> {
    // TODO: Replace with @tauri-apps/plugin-notification sendNotification()
    throw new Error(
      "DesktopNotificationPort not implemented — add @tauri-apps/plugin-notification"
    );
  }
}
