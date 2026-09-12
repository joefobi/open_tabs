/** Persist scan submissions before network dispatch. */

import { readStorageValue, writeStorageValue } from "./storage";
import type { PendingScan, ScanAcceptedResponse, ScanCreateRequest } from "./types";

const PENDING_SCANS_KEY = "palenque.pendingScans";

export class PendingSubmissionStore {
  async list(): Promise<PendingScan[]> {
    return (await readStorageValue<PendingScan[]>(PENDING_SCANS_KEY)) ?? [];
  }

  async upsertPending(body: ScanCreateRequest): Promise<PendingScan> {
    const scans = await this.list();
    const existing = scans.find((scan) => scan.clientRequestId === body.client_request_id);
    const pending: PendingScan = existing ?? {
      clientRequestId: body.client_request_id,
      body,
      createdAt: new Date().toISOString(),
      state: "pending",
    };
    pending.body = body;
    pending.state = "pending";
    await this.write(scans.filter((scan) => scan.clientRequestId !== pending.clientRequestId).concat(pending));
    return pending;
  }

  async markSubmitted(
    clientRequestId: string,
    response: ScanAcceptedResponse,
  ): Promise<void> {
    const scans = await this.list();
    const updated = scans.map((scan) =>
      scan.clientRequestId === clientRequestId
        ? {
            ...scan,
            scanId: response.scan_id,
            state: "submitted" as const,
            lastAttemptAt: new Date().toISOString(),
          }
        : scan,
    );
    await this.write(updated);
  }

  async markAttempt(clientRequestId: string): Promise<void> {
    const scans = await this.list();
    const updated = scans.map((scan) =>
      scan.clientRequestId === clientRequestId
        ? { ...scan, lastAttemptAt: new Date().toISOString() }
        : scan,
    );
    await this.write(updated);
  }

  async remove(clientRequestId: string): Promise<void> {
    const scans = await this.list();
    await this.write(scans.filter((scan) => scan.clientRequestId !== clientRequestId));
  }

  private async write(scans: PendingScan[]): Promise<void> {
    await writeStorageValue(PENDING_SCANS_KEY, scans);
  }
}
