"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { WifiOff } from "lucide-react";

/**
 * Displays an offline badge when the browser has no network connection.
 * Per CLAUDE.md: never show error screens for network issues, show this instead.
 * @returns Offline indicator badge or null
 */
export function OfflineIndicator() {
  const t = useTranslations("common");
  const [isOffline, setIsOffline] = useState(false);

  useEffect(() => {
    setIsOffline(!navigator.onLine);

    const handleOffline = () => setIsOffline(true);
    const handleOnline = () => setIsOffline(false);

    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);

    return () => {
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
    };
  }, []);

  if (!isOffline) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-lg bg-warning px-3 py-2 text-sm font-medium text-warning-foreground shadow-lg dark:bg-warning dark:text-warning-foreground">
      <WifiOff className="h-4 w-4" />
      {t("offline")}
    </div>
  );
}
