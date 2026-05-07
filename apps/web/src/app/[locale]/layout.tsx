import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { ThemeProvider } from "@/components/providers/ThemeProvider";
import { AuthProvider } from "@/components/providers/AuthProvider";
import { SyncProvider } from "@/components/providers/SyncProvider";
import { OfflineIndicator } from "@/components/ui/OfflineIndicator";
import { AppShell } from "@/components/layout/AppShell";
import { HelpBot } from "@/components/HelpBot";
import "@/app/globals.css";

export const metadata: Metadata = {
  title: "Aifya — Hospital Management System",
  description: "AI-Native Hospital Management System for Kenyan hospitals",
};

/**
 * Root layout for the application with locale support.
 * @param props.children - Page content
 * @param props.params - Route params containing locale
 * @returns Root HTML layout
 */
export default async function RootLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  if (!routing.locales.includes(locale as "en" | "sw")) {
    notFound();
  }

  const messages = await getMessages();

  return (
    <html lang={locale} suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">
        <ThemeProvider>
          <NextIntlClientProvider messages={messages}>
            <QueryProvider>
              <AuthProvider>
                <SyncProvider>
                  <AppShell>{children}</AppShell>
                  <OfflineIndicator />
                  <HelpBot />
                </SyncProvider>
              </AuthProvider>
            </QueryProvider>
          </NextIntlClientProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
