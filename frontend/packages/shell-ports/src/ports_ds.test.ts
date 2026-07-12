/**
 * Type-check test for Shell Port interfaces and implementations.
 *
 * This file is never executed at runtime — it exists to verify that
 * all implementations satisfy their interface contracts at the type level.
 * Run: tsc --noEmit --strict src/ports_ds.test.ts
 */

import type {
  FilePort,
  FileHandle,
  FileOpenOptions,
  FileFilter,
  CameraPort,
  CameraCapture,
  CameraOptions,
  ScannerPort,
  ScannerOptions,
  AudioPort,
  AudioRecording,
  AudioOptions,
  NotificationPort,
  NotificationOptions,
  NotificationLevel,
} from "./ports_ds.js";

import {
  WebFilePort,
  WebCameraPort,
  WebScannerPort,
  WebAudioPort,
  WebNotificationPort,
} from "./web_ds.js";

import {
  DesktopFilePort,
  DesktopCameraPort,
  DesktopScannerPort,
  DesktopAudioPort,
  DesktopNotificationPort,
} from "./desktop_ds.js";

// ─── Type-level assignment checks ────────────────────────────────────────────
// These compile-time assertions confirm that each implementation class
// satisfies the corresponding interface.

const _webFilePort: FilePort = new WebFilePort();
const _webCameraPort: CameraPort = new WebCameraPort();
const _webScannerPort: ScannerPort = new WebScannerPort();
const _webAudioPort: AudioPort = new WebAudioPort();
const _webNotificationPort: NotificationPort = new WebNotificationPort();

const _desktopFilePort: FilePort = new DesktopFilePort();
const _desktopCameraPort: CameraPort = new DesktopCameraPort();
const _desktopScannerPort: ScannerPort = new DesktopScannerPort();
const _desktopAudioPort: AudioPort = new DesktopAudioPort();
const _desktopNotificationPort: NotificationPort = new DesktopNotificationPort();

// ─── Type alias re-exports (structural) ──────────────────────────────────────
// Ensures every type in ports_ds.ts is importable from index_ds.ts.

const _filter: FileFilter = { name: "Images", extensions: [".png", ".jpg"] };
const _openOpts: FileOpenOptions = { multiple: true, filters: [_filter] };
const _cameraOpts: CameraOptions = { width: 1920, height: 1080 };
const _scanOpts: ScannerOptions = { resolution: 300, colorMode: "color" };
const _audioOpts: AudioOptions = { sampleRate: 44100 };
const _level: NotificationLevel = "info";
const _notifyOpts: NotificationOptions = {
  title: "Test",
  body: "Hello",
  level: _level,
  timeoutMs: 5000,
};

// ─── Structural checks ───────────────────────────────────────────────────────

// FileHandle read returns Promise<Uint8Array>
const _fileHandle: FileHandle = {} as FileHandle;
const _bytes: Promise<Uint8Array> = _fileHandle.read();

// CameraCapture has dataUrl, width, height
const _capture: CameraCapture = { dataUrl: "", width: 640, height: 480 };
void _capture;

// AudioRecording has blob and durationMs
const _recording: AudioRecording = { blob: new Blob(), durationMs: 1000 };
void _recording;

console.log("All type checks passed.");
