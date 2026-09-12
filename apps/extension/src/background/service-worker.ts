/** Service worker entry point for the extension middle layer. */

import { ApiClient } from "./apiClient";
import { CredentialStore } from "./credentials";
import { PendingSubmissionStore } from "./pendingSubmissions";
import { ExtensionRuntimeError, ScanOrchestrator } from "./scanOrchestrator";
import { TabScanner } from "./tabScanner";
import type { ChromeApi, ExtensionMessage } from "./types";

declare const chrome: ChromeApi;

const DEFAULT_API_BASE_URL = "http://localhost:8000";
const OBSERVATION_FLUSH_DEBOUNCE_MS = 2_000;
const OBSERVATION_REFRESH_ALARM = "refreshChangedObservations";
const OBSERVATION_REFRESH_MINUTES = 5;

const credentials = new CredentialStore();
const apiClient = new ApiClient(DEFAULT_API_BASE_URL, () => credentials.getToken());
const orchestrator = new ScanOrchestrator(apiClient, new PendingSubmissionStore(), new TabScanner());
let observationFlushTimer: ReturnType<typeof setTimeout> | undefined;

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  void handleMessage(message)
    .then((response) => sendResponse({ ok: true, response }))
    .catch((error: unknown) =>
      sendResponse({
        ok: false,
        error: serializeError(error),
      }),
    );
  return true;
});

registerObservationTriggers();

void credentials
  .ensureCredential(apiClient)
  .then(() => orchestrator.retryPending())
  .then(() => scheduleObservationFlush())
  .catch((error: unknown) =>
    console.warn("Unable to start observation collection.", error),
  );

async function handleMessage(message: ExtensionMessage): Promise<unknown> {
  await credentials.ensureCredential(apiClient);

  switch (message.type) {
    case "GET_SCAN":
      return apiClient.getScan(message.scanId);
    case "LIST_TASKS":
      return apiClient.listTasks();
    case "ADD_MANUAL_TASK":
      return apiClient.createManualTask({
        client_request_id: message.clientRequestId,
        title: message.title,
      });
    case "UPDATE_MANUAL_TASK":
      return apiClient.updateManualTask(message.taskId, message.patch);
    case "DELETE_TASK":
      await apiClient.deleteTask(message.taskId);
      return { deleted: true };
    case "CLEAR_DATA":
      return apiClient.clearData();
    case "OPEN_TASK_SOURCE":
      return openTaskSource(message.tabId, message.url);
  }
}

function registerObservationTriggers(): void {
  chrome.runtime.onInstalled?.addListener(() => scheduleObservationFlush());
  chrome.runtime.onStartup?.addListener(() => scheduleObservationFlush());
  chrome.alarms?.create(OBSERVATION_REFRESH_ALARM, {
    delayInMinutes: OBSERVATION_REFRESH_MINUTES,
    periodInMinutes: OBSERVATION_REFRESH_MINUTES,
  });
  chrome.alarms?.onAlarm.addListener((alarm) => {
    if (alarm.name === OBSERVATION_REFRESH_ALARM) {
      scheduleObservationFlush();
    }
  });
  chrome.tabs.onActivated?.addListener(() => scheduleObservationFlush());
  chrome.tabs.onUpdated?.addListener((_tabId, changeInfo, tab) => {
    if (
      changeInfo.status === "complete" ||
      changeInfo.url !== undefined ||
      tab.status === "complete"
    ) {
      scheduleObservationFlush();
    }
  });
}

function scheduleObservationFlush(): void {
  if (observationFlushTimer !== undefined) {
    clearTimeout(observationFlushTimer);
  }

  observationFlushTimer = setTimeout(() => {
    observationFlushTimer = undefined;
    void flushChangedObservations();
  }, OBSERVATION_FLUSH_DEBOUNCE_MS);
}

async function flushChangedObservations(): Promise<void> {
  try {
    await credentials.ensureCredential(apiClient);
    await orchestrator.retryPending();
    await orchestrator.submitOpenTabObservations();
  } catch (error: unknown) {
    if (error instanceof ExtensionRuntimeError && error.code === "no_scannable_tabs") {
      return;
    }
    console.warn("Unable to flush changed observations.", error);
  }
}

async function openTaskSource(tabId: number | undefined, url: string): Promise<{ opened: boolean }> {
  if (tabId !== undefined) {
    try {
      const existing = await chrome.tabs.get(tabId);
      if (existing.url === url) {
        await chrome.tabs.update(tabId, { active: true });
        return { opened: true };
      }
    } catch {
      // Fall through to reopen by URL when the session tab mapping is stale.
    }
  }
  try {
    const target = new URL(url);
    if (target.protocol !== "http:" && target.protocol !== "https:") {
      return { opened: false };
    }
    await chrome.tabs.create({ url, active: true });
    return { opened: true };
  } catch {
    return { opened: false };
  }
}

function serializeError(error: unknown): { code: string; message: string; retryable: boolean } {
  if (error instanceof Error && "code" in error && "retryable" in error) {
    return {
      code: String(error.code),
      message: error.message,
      retryable: Boolean(error.retryable),
    };
  }
  return {
    code: "extension_error",
    message: error instanceof Error ? error.message : "Unexpected extension error.",
    retryable: true,
  };
}
