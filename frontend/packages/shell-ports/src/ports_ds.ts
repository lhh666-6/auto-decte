/**
 * Shell Port interfaces.
 *
 * These abstract platform-specific capabilities (file system, camera,
 * scanner, audio, notifications) behind a common TypeScript interface.
 *
 * Two implementations exist:
 *   - web_ds.ts     — browser APIs (File API, MediaDevices, Notification API)
 *   - desktop_ds.ts — Tauri shell APIs (stubs, no @tauri-apps/* import)
 *
 * Conventions:
 *   - All port methods return Promise to support both sync and async backends.
 *   - File/Blob types use standard Web API types (File, Blob, Uint8Array).
 *   - MIME type strings are used where a specific media type is needed.
 */

// ─── File Port ───────────────────────────────────────────────────────────────

export interface FileFilter {
  name: string;
  extensions: string[];
}

export interface FileOpenOptions {
  /** Whether the user may select multiple files. */
  multiple?: boolean;
  /** Accepted MIME types or file extensions. */
  filters?: FileFilter[];
}

export interface FileHandle {
  name: string;
  size: number;
  mimeType: string;
  read(): Promise<Uint8Array>;
}

export interface FilePort {
  /** Open a native file-picker dialog and return selected file handles. */
  open(options?: FileOpenOptions): Promise<FileHandle[]>;

  /** Read file content by handle (convenience wrapper). */
  read(handle: FileHandle): Promise<Uint8Array>;
}

// ─── Camera Port ─────────────────────────────────────────────────────────────

export interface CameraOptions {
  /** Preferred camera device ID (from enumerateDevices). */
  deviceId?: string;
  /** Desired video width in pixels. */
  width?: number;
  /** Desired video height in pixels. */
  height?: number;
}

export interface CameraCapture {
  /** Image as a data URL (base64-encoded). */
  dataUrl: string;
  /** Image width in pixels. */
  width: number;
  /** Image height in pixels. */
  height: number;
}

export interface CameraPort {
  /** Request camera access and return a capture handle. */
  initialize(options?: CameraOptions): Promise<void>;

  /** Capture a single frame from the camera stream. */
  capture(): Promise<CameraCapture>;

  /** Release the camera stream. */
  release(): Promise<void>;
}

// ─── Scanner Port ────────────────────────────────────────────────────────────

export interface ScannerOptions {
  /** Which scanner device to use (empty = system default). */
  deviceName?: string;
  /** DPI for the scan. */
  resolution?: number;
  /** Colour mode: "color" | "grayscale" | "bw". */
  colorMode?: "color" | "grayscale" | "bw";
}

export interface ScannerPort {
  /** Detect available scanner devices. */
  listDevices(): Promise<string[]>;

  /** Scan a document and return raw image data. */
  scan(options?: ScannerOptions): Promise<Uint8Array>;
}

// ─── Audio Port ──────────────────────────────────────────────────────────────

export interface AudioOptions {
  /** Preferred audio input device ID. */
  deviceId?: string;
  /** Sample rate in Hz (e.g. 44100). */
  sampleRate?: number;
}

export interface AudioRecording {
  /** WAV or other audio format as a Blob. */
  blob: Blob;
  /** Duration in seconds. */
  durationMs: number;
}

export interface AudioPort {
  /** Start recording from the microphone. */
  startRecording(options?: AudioOptions): Promise<void>;

  /** Stop recording and return the captured audio. */
  stopRecording(): Promise<AudioRecording>;

  /** Play back audio from a blob. */
  play(blob: Blob): Promise<void>;
}

// ─── Notification Port ───────────────────────────────────────────────────────

export type NotificationLevel = "info" | "warning" | "error" | "success";

export interface NotificationOptions {
  title: string;
  body: string;
  level?: NotificationLevel;
  /** Milliseconds before auto-dismiss (0 = no auto-dismiss). */
  timeoutMs?: number;
  /** Optional action label shown on a clickable notification. */
  actionLabel?: string;
}

export interface NotificationPort {
  /** Display a notification. Returns true if the user clicked it. */
  notify(options: NotificationOptions): Promise<boolean>;
}
