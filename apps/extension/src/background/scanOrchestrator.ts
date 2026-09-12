/** Coordinate tab scanning, pending persistence, and scan submission. */

import type { ApiClient } from "./apiClient";
import type { PendingSubmissionStore } from "./pendingSubmissions";
import type { TabScanner } from "./tabScanner";
import type { CollectedPage, ObservationPayload, ScanAcceptedResponse, ScanCreateRequest } from "./types";

export class ScanOrchestrator {
  private readonly apiClient: ApiClient;
  private readonly pendingStore: PendingSubmissionStore;
  private readonly tabScanner: TabScanner;

  constructor(apiClient: ApiClient, pendingStore: PendingSubmissionStore, tabScanner: TabScanner) {
    this.apiClient = apiClient;
    this.pendingStore = pendingStore;
    this.tabScanner = tabScanner;
  }

  async submitOpenTabObservations(): Promise<ScanAcceptedResponse> {
    const pages = await this.tabScanner.scanOpenTabs();
    if (pages.length === 0) {
      throw new ExtensionRuntimeError(
        "no_scannable_tabs",
        "No HTTP(S) tabs are available to scan.",
        false,
      );
    }

    const body = buildScanRequest(pages);
    await this.pendingStore.upsertPending(body);
    await this.pendingStore.markAttempt(body.client_request_id);
    const response = await this.apiClient.createScan(body);
    await this.pendingStore.markSubmitted(body.client_request_id, response);
    return response;
  }

  async retryPending(): Promise<ScanAcceptedResponse[]> {
    const pending = await this.pendingStore.list();
    const responses: ScanAcceptedResponse[] = [];
    for (const scan of pending.filter((item) => item.state === "pending")) {
      await this.pendingStore.markAttempt(scan.clientRequestId);
      const response = await this.apiClient.createScan(scan.body);
      await this.pendingStore.markSubmitted(scan.clientRequestId, response);
      responses.push(response);
    }
    return responses;
  }
}

function buildScanRequest(pages: CollectedPage[]): ScanCreateRequest {
  const clientRequestId = crypto.randomUUID();
  return {
    client_request_id: clientRequestId,
    observations: pages.map((page) => toObservationPayload(clientRequestId, page)),
  };
}

function toObservationPayload(clientRequestId: string, page: CollectedPage): ObservationPayload {
  return {
    client_observation_id: `${clientRequestId}:${page.tabId}:${page.contentHash.slice(0, 16)}`,
    source_url: page.url,
    title: page.title,
    observed_at: page.observedAt,
    text: page.text,
    extraction_state: page.extractionState,
    truncated: page.truncated,
  };
}

export class ExtensionRuntimeError extends Error {
  readonly code: string;
  readonly retryable: boolean;

  constructor(code: string, message: string, retryable: boolean) {
    super(message);
    this.name = "ExtensionRuntimeError";
    this.code = code;
    this.retryable = retryable;
  }
}
