import { useState } from "react";
import { motion } from "framer-motion";
import { getApiToken, setApiToken } from "../lib/api";
import { normalizeUrl } from "../lib/url";

interface RunFormProps {
  busy: boolean;
  onRun: (url: string, instructions: string) => void;
  onLoadMockData?: () => void;
}

const INSULTS = [
  "where is the web address idiot?",
  "feed me a target URL, not empty air.",
  "invalid target. did your keyboard break?",
  "error: target url missing. please plug in your brain.",
  "verity run: target URL is required, genius.",
  "404: web address not found in your head.",
  "how do I test a ghost target?",
  "enter a target URL or go grab some coffee first.",
  "even an AI cannot run tests on empty text."
];

export function RunForm({ busy, onRun, onLoadMockData }: RunFormProps) {
  const [url, setUrl] = useState("");
  const [instructions, setInstructions] = useState("");
  const [showInstructions, setShowInstructions] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [token, setToken] = useState(getApiToken);
  const [error, setError] = useState<string | null>(null);

  function submit() {
    const normalized = normalizeUrl(url);
    if (!normalized) {
      const randomMsg = INSULTS[Math.floor(Math.random() * INSULTS.length)];
      setError(randomMsg);
      return;
    }
    setError(null);
    setApiToken(token.trim());
    onRun(normalized, instructions.trim());
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="mx-auto w-full max-w-xl"
    >
      {/* Terminal window frame */}
      <div className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm dark:border-border-dark dark:bg-card-dark">
        {/* Terminal Header Bar */}
        <div className="flex items-center justify-between border-b border-stone-150 bg-stone-50 px-4 py-2.5 dark:border-border-dark dark:bg-[#161412] select-none">
          <div className="flex items-center gap-1.5">
            <span className="h-3 w-3 rounded-full bg-rose-500/80" />
            <span className="h-3 w-3 rounded-full bg-amber-500/80" />
            <span className="h-3 w-3 rounded-full bg-emerald-500/80" />
          </div>
          <span className="font-mono text-xs text-stone-400 dark:text-stone-500">verity-runner</span>
          <div className="w-12" /> {/* Spacer */}
        </div>

        {/* Terminal Card Body */}
        <div className="p-6 sm:p-8 space-y-6">
          <div>
            <h2 className="text-xl font-bold tracking-tight text-stone-900 dark:text-stone-100">
              Test a website
            </h2>
            <p className="mt-1.5 text-sm text-stone-500 dark:text-stone-400">
              Give Verity a URL. It plans browser tests, runs them, and writes a report.
            </p>
          </div>

          <div className="space-y-4">
            {/* Terminal Prompt Input Line */}
            <div>
              <label
                htmlFor="url"
                className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-stone-500 dark:text-stone-400 font-mono"
              >
                Target URL
              </label>
              <div className="rounded-xl border border-stone-300 dark:border-border-dark bg-stone-50 dark:bg-bg-dark flex items-center px-3.5 py-2.5 font-mono text-sm focus-within:border-stone-500 focus-within:ring-4 focus-within:ring-stone-500/15 transition">
                <span className="text-stone-400 dark:text-stone-500 select-none mr-2 font-bold">$ verity run</span>
                <input
                  id="url"
                  type="text"
                  value={url}
                  autoFocus
                  placeholder="https://example.com"
                  onChange={(e) => setUrl(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && submit()}
                  className="flex-1 bg-transparent text-stone-900 dark:text-stone-100 outline-none placeholder:text-stone-400/50 dark:placeholder:text-stone-500/50"
                />
              </div>
            </div>

            {/* CLI Flags Arguments toggles */}
            <div className="flex flex-wrap gap-2 pt-1">
              <button
                type="button"
                onClick={() => setShowInstructions((prev) => !prev)}
                className={`rounded-lg border px-3 py-1.5 text-xs font-mono font-medium transition ${
                  showInstructions
                    ? "bg-[#3e3a37] text-white border-[#3e3a37] dark:bg-stone-100 dark:text-stone-950 dark:border-stone-100"
                    : "border-stone-200 text-stone-500 hover:bg-stone-50 dark:border-border-dark dark:text-stone-400 dark:hover:bg-border-dark/60"
                }`}
              >
                {showInstructions ? "--instructions" : "+ instructions"}
              </button>
              <button
                type="button"
                onClick={() => setShowAdvanced((prev) => !prev)}
                className={`rounded-lg border px-3 py-1.5 text-xs font-mono font-medium transition ${
                  showAdvanced
                    ? "bg-[#3e3a37] text-white border-[#3e3a37] dark:bg-stone-100 dark:text-stone-950 dark:border-stone-100"
                    : "border-stone-200 text-stone-500 hover:bg-stone-50 dark:border-border-dark dark:text-stone-400 dark:hover:bg-border-dark/60"
                }`}
              >
                {showAdvanced ? "--api-token" : "+ api-token"}
              </button>
            </div>

            {/* Instructions flag body */}
            {showInstructions && (
              <div className="space-y-1.5 animate-fadeIn">
                <label
                  htmlFor="instructions"
                  className="block text-xs font-medium text-stone-500 dark:text-stone-400 font-mono"
                >
                  --instructions flag body
                </label>
                <textarea
                  id="instructions"
                  value={instructions}
                  rows={3}
                  placeholder="Define scope, credentials, or constraints for the browser tests..."
                  onChange={(e) => setInstructions(e.target.value)}
                  className="w-full resize-y rounded-xl border border-stone-300 bg-white px-3.5 py-2.5 text-sm text-stone-900 outline-none transition placeholder:text-stone-400 focus:border-stone-500 focus:ring-4 focus:ring-stone-500/15 dark:border-border-dark dark:bg-bg-dark dark:text-stone-100 dark:placeholder:text-stone-500"
                />
              </div>
            )}

            {/* API token flag value */}
            {showAdvanced && (
              <div className="space-y-1.5 animate-fadeIn">
                <label
                  htmlFor="token"
                  className="block text-xs font-medium text-stone-500 dark:text-stone-400 font-mono"
                >
                  --api-token value
                </label>
                <input
                  id="token"
                  type="password"
                  value={token}
                  placeholder="Enter API token for protected endpoints..."
                  onChange={(e) => setToken(e.target.value)}
                  className="w-full rounded-xl border border-stone-300 bg-white px-3.5 py-2.5 text-sm text-stone-900 outline-none transition placeholder:text-stone-400 focus:border-stone-500 focus:ring-4 focus:ring-stone-500/15 dark:border-border-dark dark:bg-bg-dark dark:text-stone-100 dark:placeholder:text-stone-500"
                />
              </div>
            )}

            {error && (
              <p className="text-sm text-rose-800 dark:text-rose-600 font-mono pl-1.5">{error}</p>
            )}

            <div className="pt-2 space-y-3">
              <button
                type="button"
                disabled={busy}
                onClick={submit}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#3e3a37] px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-stone-850 focus:outline-none focus:ring-4 focus:ring-stone-500/15 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-stone-100 dark:text-stone-900 dark:hover:bg-stone-200"
              >
                {busy ? "Running…" : "Run tests"}
              </button>

              {onLoadMockData && (
                <button
                  type="button"
                  onClick={onLoadMockData}
                  className="text-xs font-mono text-stone-400 hover:text-stone-600 dark:text-stone-500 dark:hover:text-stone-300 transition duration-150 w-full text-center cursor-pointer py-1"
                >
                  ⚡ Load demo/sample data to preview UI layout
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
