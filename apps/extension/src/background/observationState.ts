/** Persist the latest submitted content fingerprint for each observed source. */

import { readStorageValue, writeStorageValue } from "./storage";
import type { CollectedPage, ObservationFingerprint } from "./types";

const SUBMITTED_OBSERVATIONS_KEY = "palenque.submittedObservations";
const MAX_SUBMITTED_OBSERVATIONS = 500;

export class ObservationStateStore {
  async filterChanged(
    pages: CollectedPage[],
    queuedFingerprints: ObservationFingerprint[] = [],
  ): Promise<CollectedPage[]> {
    const submitted = await this.list();
    const submittedBySource = new Map(
      submitted.map((item) => [item.sourceKey, item.contentHash]),
    );
    const queuedKeys = new Set(queuedFingerprints.map(fingerprintKey));
    return pages.filter((page) => {
      const fingerprint = toObservationFingerprint(page);
      return (
        submittedBySource.get(fingerprint.sourceKey) !== fingerprint.contentHash &&
        !queuedKeys.has(fingerprintKey(fingerprint))
      );
    });
  }

  async markSubmittedPages(pages: CollectedPage[]): Promise<void> {
    await this.markSubmittedFingerprints(pages.map(toObservationFingerprint));
  }

  async markSubmittedFingerprints(fingerprints: ObservationFingerprint[]): Promise<void> {
    if (fingerprints.length === 0) {
      return;
    }

    const submitted = await this.list();
    const submittedBySource = new Map(
      submitted.map((item) => [item.sourceKey, item]),
    );
    const submittedAt = new Date().toISOString();
    for (const fingerprint of fingerprints) {
      submittedBySource.set(fingerprint.sourceKey, {
        ...fingerprint,
        submittedAt,
      });
    }

    const pruned = Array.from(submittedBySource.values())
      .sort((left, right) => (right.submittedAt ?? "").localeCompare(left.submittedAt ?? ""))
      .slice(0, MAX_SUBMITTED_OBSERVATIONS);
    await writeStorageValue(SUBMITTED_OBSERVATIONS_KEY, pruned);
  }

  private async list(): Promise<ObservationFingerprint[]> {
    return (await readStorageValue<ObservationFingerprint[]>(SUBMITTED_OBSERVATIONS_KEY)) ?? [];
  }
}

export function toObservationFingerprint(page: CollectedPage): ObservationFingerprint {
  return {
    sourceKey: sourceKeyForUrl(page.url),
    contentHash: page.contentHash,
  };
}

function sourceKeyForUrl(url: string): string {
  try {
    const parsed = new URL(url);
    parsed.hash = "";
    return parsed.toString();
  } catch {
    return url.trim();
  }
}

function fingerprintKey(fingerprint: ObservationFingerprint): string {
  return `${fingerprint.sourceKey}\n${fingerprint.contentHash}`;
}
