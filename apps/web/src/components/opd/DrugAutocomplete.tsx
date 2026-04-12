"use client";

import { useState, useRef, useEffect } from "react";
import { useTranslations } from "next-intl";
import { Search, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Common drugs in Kenyan clinical settings with KEML (Kenya Essential Medicines List) flag.
 * Full drug search will be backed by the AI service / drug database in production.
 */
const COMMON_DRUGS: { name: string; generic: string; isKeml: boolean }[] = [
  { name: "Paracetamol 500mg", generic: "Paracetamol", isKeml: true },
  { name: "Amoxicillin 500mg", generic: "Amoxicillin", isKeml: true },
  { name: "Metformin 500mg", generic: "Metformin", isKeml: true },
  { name: "Amlodipine 5mg", generic: "Amlodipine", isKeml: true },
  { name: "Omeprazole 20mg", generic: "Omeprazole", isKeml: true },
  { name: "Artemether/Lumefantrine (AL)", generic: "Artemether-Lumefantrine", isKeml: true },
  { name: "Diclofenac 50mg", generic: "Diclofenac", isKeml: true },
  { name: "Ciprofloxacin 500mg", generic: "Ciprofloxacin", isKeml: true },
  { name: "Metronidazole 400mg", generic: "Metronidazole", isKeml: true },
  { name: "Salbutamol Inhaler", generic: "Salbutamol", isKeml: true },
  { name: "Hydrochlorothiazide 25mg", generic: "Hydrochlorothiazide", isKeml: true },
  { name: "Enalapril 10mg", generic: "Enalapril", isKeml: true },
  { name: "Ibuprofen 400mg", generic: "Ibuprofen", isKeml: true },
  { name: "Doxycycline 100mg", generic: "Doxycycline", isKeml: true },
  { name: "Prednisolone 5mg", generic: "Prednisolone", isKeml: true },
  { name: "Cotrimoxazole 960mg", generic: "Sulfamethoxazole/Trimethoprim", isKeml: true },
  { name: "Azithromycin 500mg", generic: "Azithromycin", isKeml: true },
  { name: "Losartan 50mg", generic: "Losartan", isKeml: true },
  { name: "Atorvastatin 20mg", generic: "Atorvastatin", isKeml: false },
  { name: "Ceftriaxone 1g", generic: "Ceftriaxone", isKeml: true },
  { name: "ORS (Oral Rehydration Salts)", generic: "ORS", isKeml: true },
  { name: "Zinc 20mg", generic: "Zinc Sulfate", isKeml: true },
  { name: "Ferrous Sulfate 200mg", generic: "Ferrous Sulfate", isKeml: true },
  { name: "Folic Acid 5mg", generic: "Folic Acid", isKeml: true },
  { name: "Insulin (Soluble) 100IU/ml", generic: "Insulin", isKeml: true },
];

interface DrugAutocompleteProps {
  onSelect: (drugName: string, genericName: string | null, isKeml: boolean) => void;
}

/**
 * Drug autocomplete with KEML flag.
 * Highlights KEML drugs per CLAUDE.md requirements.
 *
 * @param props - onSelect callback with drug info
 * @returns Drug autocomplete input
 */
export function DrugAutocomplete({ onSelect }: DrugAutocompleteProps) {
  const t = useTranslations("prescription");
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [selectedDisplay, setSelectedDisplay] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  const filtered = query.length >= 2
    ? COMMON_DRUGS.filter(
        (drug) =>
          drug.name.toLowerCase().includes(query.toLowerCase()) ||
          drug.generic.toLowerCase().includes(query.toLowerCase())
      ).slice(0, 10)
    : [];

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (drug: typeof COMMON_DRUGS[0]) => {
    setSelectedDisplay(drug.name);
    setQuery("");
    setIsOpen(false);
    onSelect(drug.name, drug.generic, drug.isKeml);
  };

  return (
    <div ref={containerRef} className="relative">
      <label className="mb-1 block text-xs font-medium text-muted-foreground">
        {t("drugName")}
      </label>
      {selectedDisplay ? (
        <div
          onClick={() => { setSelectedDisplay(""); setIsOpen(true); }}
          className="flex cursor-pointer items-center gap-2 rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
        >
          <span>{selectedDisplay}</span>
        </div>
      ) : (
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setIsOpen(true); }}
            onFocus={() => query.length >= 2 && setIsOpen(true)}
            placeholder={t("drugSearch")}
            className="w-full rounded-md border border-input bg-background py-1.5 pl-8 pr-2.5 text-sm text-foreground dark:border-border dark:bg-background"
          />
        </div>
      )}

      {isOpen && filtered.length > 0 && (
        <ul className="absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-md border border-border bg-card shadow-lg dark:bg-card">
          {filtered.map((drug) => (
            <li key={drug.name}>
              <button
                type="button"
                onClick={() => handleSelect(drug)}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted dark:hover:bg-muted"
              >
                <span className="flex-1 text-foreground">{drug.name}</span>
                <span className="text-xs text-muted-foreground">{drug.generic}</span>
                {drug.isKeml && (
                  <span className="flex items-center gap-0.5 rounded-full bg-green-100 px-1.5 py-0.5 text-xs font-medium text-green-800 dark:bg-green-950 dark:text-green-200">
                    <ShieldCheck className="h-3 w-3" />
                    {t("keml")}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
