/** Store and mint anonymous installation credentials for API calls. */

import type { ApiClient } from "./apiClient";
import { readStorageValue, writeStorageValue } from "./storage";
import type { InstallationCredential } from "./types";

const CREDENTIAL_KEY = "palenque.installationCredential";

export class CredentialStore {
  async getCredential(): Promise<InstallationCredential | null> {
    return readStorageValue<InstallationCredential>(CREDENTIAL_KEY);
  }

  async getToken(): Promise<string | null> {
    const credential = await this.getCredential();
    return credential?.installationToken ?? null;
  }

  async ensureCredential(apiClient: ApiClient): Promise<InstallationCredential> {
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
