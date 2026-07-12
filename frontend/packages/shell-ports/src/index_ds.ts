/**
 * Shell Ports — re-exports.
 */

// Types
export type {
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

// Web implementations
export { WebFilePort, WebCameraPort, WebScannerPort, WebAudioPort, WebNotificationPort } from "./web_ds.js";

// Desktop stub implementations
export {
  DesktopFilePort,
  DesktopCameraPort,
  DesktopScannerPort,
  DesktopAudioPort,
  DesktopNotificationPort,
} from "./desktop_ds.js";
