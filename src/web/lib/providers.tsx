"use client";

import { MsalProvider } from "@azure/msal-react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { msal } from "./api";

export function Providers({ children }: { children: ReactNode }) {
  const [qc] = useState(() => new QueryClient());
  return (
    <MsalProvider instance={msal}>
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    </MsalProvider>
  );
}
