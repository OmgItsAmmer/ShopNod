'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'next-themes';
import { useState } from 'react';
import { Toaster } from 'sonner';
import { ApiError } from '@/lib/api';

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 10_000,
            refetchOnWindowFocus: true,
            // Do not hammer the API when it says no (401/403/404/422); retry only network and 5xx errors.
            retry: (count, err) => (err instanceof ApiError && err.status > 0 && err.status < 500 ? false : count < 2),
          },
        },
      }),
  );
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <QueryClientProvider client={client}>
        {children}
        <Toaster position="top-center" richColors closeButton toastOptions={{ className: 'text-base' }} />
      </QueryClientProvider>
    </ThemeProvider>
  );
}
