/** Collect bounded readable text from the currently loaded page. */

import type { ExtractionState } from "../background/types";

export interface ExtractedPageContent {
  text: string;
  extractionState: ExtractionState;
  truncated: boolean;
}

export function collectReadablePageText(): ExtractedPageContent {
  const maxTextCharacters = 12_000;
  const blockedTags = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "SVG", "CANVAS"]);
  const contentSelectors = ["main", "article", "[role='main']", "body"];

  function normalizeWhitespace(value: string): string {
    return value.replace(/\s+/g, " ").trim();
  }

  function findReadableRoot(): Element | null {
    for (const selector of contentSelectors) {
      const element = document.querySelector(selector);
      if (element) {
        return element;
      }
    }
    return document.body;
  }

  function acceptsTextNode(node: Node): boolean {
    const parent = node.parentElement;
    if (!parent || blockedTags.has(parent.tagName)) {
      return false;
    }
    if (parent.closest("[hidden], [aria-hidden='true'], script, style, noscript")) {
      return false;
    }
    if (parent.closest("input, textarea, select, [contenteditable='true']")) {
      return false;
    }
    const style = window.getComputedStyle(parent);
    if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) {
      return false;
    }
    return Boolean(normalizeWhitespace(node.textContent ?? ""));
  }

  function collectLabels(rootElement: Element): string[] {
    const labels: string[] = [];
    const controls = rootElement.querySelectorAll("a, button, [role='button']");
    for (const control of Array.from(controls).slice(0, 80)) {
      if (control.closest("[hidden], [aria-hidden='true']")) {
        continue;
      }
      const text = normalizeWhitespace(control.textContent || control.getAttribute("aria-label") || "");
      if (text) {
        labels.push(text);
      }
    }
    return labels;
  }

  const root = findReadableRoot();
  if (!root) {
    return { text: "", extractionState: "inaccessible", truncated: false };
  }

  const chunks: string[] = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      return acceptsTextNode(node) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
    },
  });

  let current = walker.nextNode();
  while (current) {
    const text = normalizeWhitespace(current.textContent ?? "");
    if (text) {
      chunks.push(text);
    }
    current = walker.nextNode();
  }

  const labels = collectLabels(root);
  const rawText = normalizeWhitespace(chunks.concat(labels).join(" "));
  const truncated = rawText.length > maxTextCharacters;
  const text = truncated ? rawText.slice(0, maxTextCharacters) : rawText;
  const extractionState = text ? "ready" : "unloaded";
  return { text, extractionState, truncated };
}
