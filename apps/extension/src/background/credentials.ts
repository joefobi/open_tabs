/** Store and mint anonymous installation credentials for API calls. */

import type { ApiClient } from "./apiClient";
import { readStorageValue, writeStorageValue } from "./storage";
import type { InstallationCredential } from "./types";

const CREDENTIAL_KEY = "palenque.installationCredential";

export class CredentialStore {
  private credentialPromise: Promise<InstallationCredential> | null = null;

  async getCredential(): Promise<InstallationCredential | null> {
    return readStorageValue<InstallationCredential>(CREDENTIAL_KEY);
  }

  async getToken(): Promise<string | null> {
    const credential = await this.getCredential();
    return credential?.installationToken ?? null;
  }

  async ensureCredential(apiClient: ApiClient): Promise<InstallationCredential> {
    if (this.credentialPromise) {
      return this.credentialPromise;
    }

    const existing = await this.getCredential();
    if (existing) {
      return existing;
    }
    if (this.credentialPromise) {
      return this.credentialPromise;
    }

    this.credentialPromise = this.createAndStoreCredential(apiClient);
    try {
      return await this.credentialPromise;
    } finally {
      this.credentialPromise = null;
    }
  }

  private async createAndStoreCredential(apiClient: ApiClient): Promise<InstallationCredential> {
    const existing = await this.getCredential();
    if (existing) {
      return existing;
    }

    const created = await apiClient.createInstallation();
    const credential: InstallationCredential = {
      ownerId: created.owner_id,
      installationToken: created.installation_credential,
      createdAt: new Date().toISOString(),
    };
    await writeStorageValue(CREDENTIAL_KEY, credential);
    return credential;
  }
}
