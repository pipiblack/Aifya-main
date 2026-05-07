"use client";

import { useEffect, useRef, useState } from "react";
import { Compass, ExternalLink, Send, Sparkles, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { apiFetch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useTour } from "@/components/help/TourProvider";

/** Suggested in-app navigation link returned by the help bot. */
interface SuggestedLink {
  label: string;
  href: string;
}

/** Help bot answer. */
interface AnswerResponse {
  answer: string;
  suggested_links: SuggestedLink[];
  confidence: number;
  model: string;
}

/** Single chat turn in the local history. */
interface ChatTurn {
  id: string;
  role: "user" | "assistant";
  text: string;
  links?: SuggestedLink[];
}

const QUICK_PROMPTS: string[] = [
  "How do I run payroll?",
  "How to record a payment?",
  "How to add a new patient?",
  "Where do I find SHA claims?",
];

/**
 * Floating AI Help Bot.
 * A FAB at the bottom-right opens a chat drawer with quick prompts and a
 * free-form question input. Chat history is session-only.
 *
 * @returns Help bot component
 */
export function HelpBot() {
  const router = useRouter();
  const t = useTranslations("helpBot");
  const { startRecommended } = useTour();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [history, open]);

  /**
   * Send a question to the help bot.
   *
   * @param queryText - Question to send
   */
  const ask = async (queryText: string) => {
    const trimmed = queryText.trim();
    if (!trimmed || pending) return;

    const userTurn: ChatTurn = {
      id: crypto.randomUUID(),
      role: "user",
      text: trimmed,
    };
    setHistory((h) => [...h, userTurn]);
    setInput("");
    setPending(true);

    try {
      const res = await apiFetch<AnswerResponse>("/api/v1/help/ask", {
        method: "POST",
        body: JSON.stringify({ query: trimmed }),
      });
      setHistory((h) => [
        ...h,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: res.answer,
          links: res.suggested_links,
        },
      ]);
    } catch {
      setHistory((h) => [
        ...h,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: t("errorFallback"),
        },
      ]);
    } finally {
      setPending(false);
    }
  };

  return (
    <>
      {/* FAB */}
      <button
        type="button"
        data-tour="help-bot"
        onClick={() => setOpen((v) => !v)}
        aria-label={t("fabLabel")}
        className={cn(
          "fixed bottom-5 right-5 z-40 flex h-12 w-12 items-center justify-center",
          "rounded-full bg-primary text-primary-foreground shadow-lg",
          "transition-transform hover:scale-105 focus-visible:outline-none",
          "focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2",
        )}
      >
        {open ? <X className="h-5 w-5" /> : <Sparkles className="h-5 w-5" />}
      </button>

      {/* Drawer */}
      {open && (
        <div
          className={cn(
            "fixed bottom-20 right-5 z-40 flex w-[min(380px,calc(100vw-2.5rem))] flex-col",
            "max-h-[min(560px,calc(100vh-7rem))] rounded-xl border border-border",
            "bg-card shadow-xl",
          )}
          role="dialog"
          aria-label={t("drawerTitle")}
        >
          <header className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              <h2 className="text-sm font-semibold text-foreground">
                {t("drawerTitle")}
              </h2>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label={t("close")}
              className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted"
            >
              <X className="h-4 w-4" />
            </button>
          </header>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
            {history.length === 0 ? (
              <div className="space-y-3">
                <p className="text-xs text-muted-foreground">{t("intro")}</p>
                <button
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    startRecommended();
                  }}
                  className="flex w-full items-center justify-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-3 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/10"
                >
                  <Compass className="h-4 w-4" />
                  {t("takeTheTour")}
                </button>
                <div className="flex flex-col gap-2">
                  {QUICK_PROMPTS.map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => ask(p)}
                      className="rounded-lg border border-input bg-background px-3 py-2 text-left text-sm transition-colors hover:bg-muted"
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              history.map((turn) => (
                <div
                  key={turn.id}
                  className={cn(
                    "flex flex-col gap-2",
                    turn.role === "user" ? "items-end" : "items-start",
                  )}
                >
                  <div
                    className={cn(
                      "max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm",
                      turn.role === "user"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-foreground",
                    )}
                  >
                    {turn.text}
                  </div>
                  {turn.role === "assistant" && turn.links && turn.links.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {turn.links.map((l) => (
                        <button
                          key={l.href}
                          type="button"
                          onClick={() => {
                            router.push(l.href);
                            setOpen(false);
                          }}
                          className="inline-flex items-center gap-1 rounded-md border border-input bg-background px-2 py-1 text-xs font-medium transition-colors hover:bg-muted"
                        >
                          <ExternalLink className="h-3 w-3" />
                          {l.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
            {pending && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Sparkles className="h-3 w-3 animate-pulse" />
                {t("thinking")}
              </div>
            )}
          </div>

          <form
            className="flex items-center gap-2 border-t border-border px-3 py-2"
            onSubmit={(e) => {
              e.preventDefault();
              ask(input);
            }}
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t("inputPlaceholder")}
              maxLength={1000}
              className="flex-1 rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            />
            <button
              type="submit"
              disabled={pending || !input.trim()}
              aria-label={t("send")}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </div>
      )}
    </>
  );
}
