/** Promise helpers for Chrome local storage. */

import type { ChromeApi } from "./types";

declare const chrome: ChromeApi;

export async function readStorageValue<T>(key: string): Promise<T | null> {
  return new Promise((resolve) => {
    chrome.storage.local.get(key, (items) => {
      resolve((items[key] as T | undefined) ?? null);
    });
  });
}

export async function writeStorageValue<T>(key: string, value: T): Promise<void> {
  return new Promise((resolve) => {
    chrome.storage.local.set({ [key]: value }, resolve);
  });
}

export async function removeStorageValue(key: string): Promise<void> {
  return new Promise((resolve) => {
    chrome.storage.local.remove(key, resolve);
  });
}
