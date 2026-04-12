"use client";

import { useState, useRef, useEffect } from "react";
import { useTranslations } from "next-intl";
import { Search } from "lucide-react";

/**
 * Common ICD-10 codes for quick access in Kenyan clinical settings.
 * Full ICD-10 search will be backed by the AI service in production.
 */
const COMMON_ICD10: { code: string; description: string }[] = [
  { code: "J06.9", description: "Acute upper respiratory infection, unspecified" },
  { code: "A09", description: "Infectious gastroenteritis and colitis, unspecified" },
  { code: "B50.9", description: "Plasmodium falciparum malaria, unspecified" },
  { code: "J18.9", description: "Pneumonia, unspecified organism" },
  { code: "N39.0", description: "Urinary tract infection, site not specified" },
  { code: "K29.7", description: "Gastritis, unspecified" },
  { code: "J45.9", description: "Asthma, unspecified" },
  { code: "I10", description: "Essential (primary) hypertension" },
  { code: "E11.9", description: "Type 2 diabetes mellitus without complications" },
  { code: "M54.5", description: "Low back pain" },
  { code: "J02.9", description: "Acute pharyngitis, unspecified" },
  { code: "B54", description: "Unspecified malaria" },
  { code: "A01.0", description: "Typhoid fever" },
  { code: "K35.8", description: "Acute appendicitis, other and unspecified" },
  { code: "L30.9", description: "Dermatitis, unspecified" },
  { code: "R50.9", description: "Fever, unspecified" },
  { code: "R51", description: "Headache" },
  { code: "J20.9", description: "Acute bronchitis, unspecified" },
  { code: "A15.0", description: "Tuberculosis of lung" },
  { code: "B20", description: "Human immunodeficiency virus [HIV] disease" },
  { code: "D64.9", description: "Anaemia, unspecified" },
  { code: "E55.9", description: "Vitamin D deficiency, unspecified" },
  { code: "O80", description: "Single spontaneous delivery" },
  { code: "K52.9", description: "Non-infective gastroenteritis and colitis, unspecified" },
  { code: "J11.1", description: "Influenza with other respiratory manifestations" },
];

interface ICD10AutocompleteProps {
  onSelect: (code: string, description: string) => void;
}

/**
 * ICD-10 autocomplete with local search against common codes.
 * Production version will call the AI service for comprehensive ICD-10 lookup.
 *
 * @param props - onSelect callback with code and description
 * @returns ICD-10 autocomplete input
 */
export function ICD10Autocomplete({ onSelect }: ICD10AutocompleteProps) {
  const t = useTranslations("diagnosis");
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [selectedDisplay, setSelectedDisplay] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  const filtered = query.length >= 2
    ? COMMON_ICD10.filter(
        (item) =>
          item.code.toLowerCase().includes(query.toLowerCase()) ||
          item.description.toLowerCase().includes(query.toLowerCase())
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

  const handleSelect = (code: string, description: string) => {
    setSelectedDisplay(`${code} — ${description}`);
    setQuery("");
    setIsOpen(false);
    onSelect(code, description);
  };

  return (
    <div ref={containerRef} className="relative">
      <label className="mb-1 block text-xs font-medium text-muted-foreground">
        {t("icd10Code")}
      </label>
      {selectedDisplay ? (
        <div
          onClick={() => { setSelectedDisplay(""); setIsOpen(true); }}
          className="flex cursor-pointer items-center gap-2 rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
        >
          <span className="font-mono text-primary">{selectedDisplay.split(" — ")[0]}</span>
          <span className="truncate text-muted-foreground">{selectedDisplay.split(" — ")[1]}</span>
        </div>
      ) : (
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setIsOpen(true); }}
            onFocus={() => query.length >= 2 && setIsOpen(true)}
            placeholder={t("icd10Search")}
            className="w-full rounded-md border border-input bg-background py-1.5 pl-8 pr-2.5 text-sm text-foreground dark:border-border dark:bg-background"
          />
        </div>
      )}

      {isOpen && filtered.length > 0 && (
        <ul className="absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-md border border-border bg-card shadow-lg dark:bg-card">
          {filtered.map((item) => (
            <li key={item.code}>
              <button
                type="button"
                onClick={() => handleSelect(item.code, item.description)}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted dark:hover:bg-muted"
              >
                <span className="font-mono font-medium text-primary">{item.code}</span>
                <span className="truncate text-foreground">{item.description}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
