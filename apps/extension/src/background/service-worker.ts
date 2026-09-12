/** Service worker entry point for the extension middle layer. */

import { ApiClient } from "./apiClient";
import { CredentialStore } from "./credentials";
import { PendingSubmissionStore } from "./pendingSubmissions";
import { ScanOrchestrator } from "./scanOrchestrator";
import { TabScanner } from "./tabScanner";
import type { ChromeApi, ExtensionMessage } from "./types";

declare const chrome: ChromeApi;

const DEFAULT_API_BASE_URL = "http://localhost:8000";

const credentials = new CredentialStore();
const apiClient = new ApiClient(DEFAULT_API_BASE_URL, () => credentials.getToken());
const orchestrator = new ScanOrchestrator(apiClient, new PendingSubmissionStore(), new TabScanner());

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

void credentials.ensureCredential(apiClient).then(() => orchestrator.retryPending());

async function handleMessage(message: ExtensionMessage): Promise<unknown> {
  await credentials.ensureCredential(apiClient);

  switch (message.type) {
    case "SCAN_NOW":
      return orchestrator.scanNow();
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

async function openTaskSource(tabId: number | undefined, url: string): Promise<{ opened: boolean }> {
  if (tabId !== undefined) {
    try {
      const existing = await chrome.tabs.get(tabId);
      if (existing.url !== url) {
        return { opened: false };
      }
      await chrome.tabs.update(tabId, { active: true });
      const tab = await chrome.tabs.get(tabId);
      if (tab.url === url) {
        return { opened: true };
      }
    } catch {
      return { opened: false };
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
