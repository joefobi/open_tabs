/** Enumerate tabs and collect page observations. */

import { collectReadablePageText, type ExtractedPageContent } from "../collector/contentExtraction";
import type { ChromeApi, ChromeTab, CollectedPage, ExtractionState } from "./types";

declare const chrome: ChromeApi;

export class TabScanner {
  async scanOpenTabs(): Promise<CollectedPage[]> {
    const tabs = await chrome.tabs.query({ currentWindow: true });
    const limitedTabs = tabs.filter(isScannableTab).slice(0, 20);
    const pages = await Promise.all(limitedTabs.map((tab) => this.scanTab(tab)));
    return pages.filter((page): page is CollectedPage => page !== null);
  }

  private async scanTab(tab: ChromeTab): Promise<CollectedPage | null> {
    if (tab.id === undefined || !tab.url) {
      return null;
    }

    const observedAt = new Date().toISOString();
    const extraction = await this.extract(tab.id);
    return {
      tabId: tab.id,
      url: tab.url,
      title: tab.title ?? "",
      observedAt,
      text: extraction.text,
      extractionState: extraction.extractionState,
      truncated: extraction.truncated,
      contentHash: await hashContent(tab.url, tab.title ?? "", extraction.text),
      errorCode: extraction.errorCode,
    };
  }

  private async extract(tabId: number): Promise<ExtractedPageContent & { errorCode?: string }> {
    try {
      const results = await chrome.scripting.executeScript<ExtractedPageContent>({
        target: { tabId },
        func: collectReadablePageText,
      });
      return results[0]?.result ?? {
        text: "",
        extractionState: "inaccessible",
        truncated: false,
      };
    } catch {
      return {
        text: "",
        extractionState: "inaccessible",
        truncated: false,
        errorCode: "content_script_unavailable",
      };
    }
  }
}

function isScannableTab(tab: ChromeTab): boolean {
  if (tab.id === undefined || tab.incognito || !tab.url) {
    return false;
  }
  try {
    const url = new URL(tab.url);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

async function hashContent(url: string, title: string, text: string): Promise<string> {
  const normalized = [url.trim(), title.trim(), text.replace(/\s+/g, " ").trim()].join("\n");
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(normalized));
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export function toExtractionState(value: string): ExtractionState {
  if (value === "ready" || value === "inaccessible" || value === "unloaded" || value === "error") {
    return value;
  }
  return "error";
}
