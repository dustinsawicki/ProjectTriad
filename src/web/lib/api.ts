"use client";

import { PublicClientApplication, EventType, AccountInfo } from "@azure/msal-browser";

const tenantId = process.env.NEXT_PUBLIC_AZURE_TENANT_ID || "common";
const clientId = process.env.NEXT_PUBLIC_AZURE_CLIENT_ID || "00000000-0000-0000-0000-000000000000";
const apiScope  = process.env.NEXT_PUBLIC_API_SCOPE || `api://${clientId}/access_as_user`;

export const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "";

export const msal = new PublicClientApplication({
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri: typeof window !== "undefined" ? window.location.origin : "/"
  },
  cache: { cacheLocation: "sessionStorage", storeAuthStateInCookie: false }
});

if (typeof window !== "undefined") {
  msal.initialize().then(() => {
    const accounts = msal.getAllAccounts();
    if (accounts.length > 0) msal.setActiveAccount(accounts[0]);
    msal.addEventCallback((e) => {
      if (e.eventType === EventType.LOGIN_SUCCESS && e.payload) {
        msal.setActiveAccount((e.payload as { account: AccountInfo }).account);
      }
    });
  });
}

export async function getAccessToken(): Promise<string | null> {
  const account = msal.getActiveAccount();
  if (!account) return null;
  try {
    const r = await msal.acquireTokenSilent({ account, scopes: [apiScope] });
    return r.accessToken;
  } catch {
    const r = await msal.acquireTokenPopup({ scopes: [apiScope] });
    return r.accessToken;
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getAccessToken();
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  headers.set("Content-Type", "application/json");
  const r = await fetch(`${apiBaseUrl}${path}`, { ...init, headers });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}
