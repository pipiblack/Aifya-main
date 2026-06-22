"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import {
  Search,
  Users,
  UserPlus,
  Stethoscope,
  Pill,
  FlaskConical,
  Receipt,
  BarChart3,
  Settings,
} from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type { PatientListResponse } from "@aifya/shared";

interface CommandItem {
  id: string;
  label: string;
  description?: string;
  icon: React.ReactNode;
  action: () => void;
  group: "patients" | "navigation";
}

/**
 * Cmd+K command palette for global search.
 * Per CLAUDE.md: primary navigation, must search patients, actions, modules.
 * @returns Command palette dialog
 */
export function CommandPalette() {
  const t = useTranslations("nav");
  const tp = useTranslations("patients");
  const tc = useTranslations("common");
  const router = useRouter();

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [patientResults, setPatientResults] = useState<CommandItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  // Keyboard shortcut: Cmd+K / Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Search patients on query change
  useEffect(() => {
    if (!query || query.length < 2) {
      setPatientResults([]);
      return;
    }

    const timeout = setTimeout(async () => {
      setIsSearching(true);
      try {
        const data = await apiClient.get<PatientListResponse>("/patients", {
          q: query,
          page: "1",
          page_size: "5",
        });
        setPatientResults(
          data.items.map((p) => ({
            id: p.id,
            label: `${p.first_name} ${p.last_name}`,
            description: `${p.mrn} · ${p.phone_number}`,
            icon: <Users className="h-4 w-4" />,
            action: () => {
              router.push(`/patients/${p.id}`);
              setOpen(false);
            },
            group: "patients" as const,
          }))
        );
      } catch {
        setPatientResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 300);

    return () => clearTimeout(timeout);
  }, [query, router]);

  // Static navigation commands
  const navigationItems: CommandItem[] = [
    { id: "nav-patients", label: tp("search"), icon: <Users className="h-4 w-4" />, action: () => { router.push("/patients"); setOpen(false); }, group: "navigation" },
    { id: "nav-register", label: tp("register"), icon: <UserPlus className="h-4 w-4" />, action: () => { router.push("/patients/register"); setOpen(false); }, group: "navigation" },
    { id: "nav-opd", label: t("opd"), icon: <Stethoscope className="h-4 w-4" />, action: () => { router.push("/opd"); setOpen(false); }, group: "navigation" },
    { id: "nav-pharmacy", label: t("pharmacy"), icon: <Pill className="h-4 w-4" />, action: () => { router.push("/pharmacy"); setOpen(false); }, group: "navigation" },
    { id: "nav-lab", label: t("laboratory"), icon: <FlaskConical className="h-4 w-4" />, action: () => { router.push("/laboratory"); setOpen(false); }, group: "navigation" },
    { id: "nav-billing", label: t("billing"), icon: <Receipt className="h-4 w-4" />, action: () => { router.push("/billing"); setOpen(false); }, group: "navigation" },
    { id: "nav-reports", label: t("reports"), icon: <BarChart3 className="h-4 w-4" />, action: () => { router.push("/reports"); setOpen(false); }, group: "navigation" },
    { id: "nav-settings", label: t("settings"), icon: <Settings className="h-4 w-4" />, action: () => { router.push("/settings"); setOpen(false); }, group: "navigation" },
  ];

  // Filter navigation by query
  const filteredNav = query
    ? navigationItems.filter((item) =>
        item.label.toLowerCase().includes(query.toLowerCase())
      )
    : navigationItems;

  const allItems = useMemo(
    () => [...patientResults, ...filteredNav],
    [patientResults, filteredNav],
  );

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, allItems.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const item = allItems[selectedIndex];
        if (item) item.action();
      }
    },
    [allItems, selectedIndex]
  );

  // Reset selection when results change
  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-50 bg-black/50"
        onClick={() => setOpen(false)}
      />

      {/* Dialog */}
      <div className="fixed left-1/2 top-[20%] z-50 w-full max-w-lg -translate-x-1/2 rounded-xl border border-border bg-card shadow-2xl dark:border-border dark:bg-card">
        {/* Search input */}
        <div className="flex items-center gap-3 border-b border-border px-4 dark:border-border">
          <Search className="h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={tc("searchPlaceholder")}
            className="flex-1 bg-transparent py-3 text-sm text-foreground outline-none placeholder:text-muted-foreground dark:text-foreground"
            autoFocus
          />
          <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 text-xs text-muted-foreground dark:border-border dark:bg-muted">
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-80 overflow-y-auto p-2">
          {isSearching && (
            <p className="px-3 py-2 text-sm text-muted-foreground">
              {tc("loading")}
            </p>
          )}

          {/* Patient results */}
          {patientResults.length > 0 && (
            <div className="mb-2">
              <p className="px-3 py-1 text-xs font-semibold uppercase text-muted-foreground">
                {tp("search")}
              </p>
              {patientResults.map((item, i) => (
                <CommandItemRow
                  key={item.id}
                  item={item}
                  isSelected={i === selectedIndex}
                  onClick={item.action}
                />
              ))}
            </div>
          )}

          {/* Navigation */}
          {filteredNav.length > 0 && (
            <div>
              <p className="px-3 py-1 text-xs font-semibold uppercase text-muted-foreground">
                {tc("actions")}
              </p>
              {filteredNav.map((item, i) => (
                <CommandItemRow
                  key={item.id}
                  item={item}
                  isSelected={i + patientResults.length === selectedIndex}
                  onClick={item.action}
                />
              ))}
            </div>
          )}

          {allItems.length === 0 && !isSearching && query.length >= 2 && (
            <p className="px-3 py-4 text-center text-sm text-muted-foreground">
              {tc("noResults")}
            </p>
          )}
        </div>
      </div>
    </>
  );
}

function CommandItemRow({
  item,
  isSelected,
  onClick,
}: {
  item: CommandItem;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
        isSelected
          ? "bg-primary/10 text-primary dark:bg-primary/10 dark:text-primary"
          : "text-foreground hover:bg-muted dark:text-foreground dark:hover:bg-muted"
      )}
    >
      <span className="text-muted-foreground">{item.icon}</span>
      <div className="flex-1 text-left">
        <p className="font-medium">{item.label}</p>
        {item.description && (
          <p className="text-xs text-muted-foreground">{item.description}</p>
        )}
      </div>
    </button>
  );
}
