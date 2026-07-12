import { useState } from "react";
import { motion } from "framer-motion";
import { getApiToken, setApiToken } from "../lib/api";
import { normalizeUrl } from "../lib/url";

interface RunFormProps {
  busy: boolean;
  onRun: (url: string, instructions: string) => void;
}

export function RunForm({ busy, onRun }: RunFormProps) {
  const [url, setUrl] = useState("");
  const [instructions, setInstructions] = useState("");
  const [showInstructions, setShowInstructions] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [token, setToken] = useState(getApiToken);
  const [error, setError] = useState<string | null>(null);

  function submit() {
    const normalized = normalizeUrl(url);
    if (!normalized) {
      setError("Enter a website to test — e.g. example.com or https://example.com");
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
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-8">
        <h2 className="text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-50">
          Test a website
        </h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Give Verity a URL. It plans browser tests, runs them, and writes a report.
        </p>

        <div className="mt-6 space-y-4">
          <div>
            <label
              htmlFor="url"
              className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300"
            >
              Target URL
            </label>
            <input
              id="url"
              type="text"
              value={url}
              autoFocus
              placeholder="https://example.com"
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && submit()}
              className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-teal-500 focus:ring-4 focus:ring-teal-500/15 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
            />
          </div>

          {showInstructions ? (
            <div>
              <label
                htmlFor="instructions"
                className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300"
              >
                Instructions <span className="font-normal text-slate-400">(optional)</span>
              </label>
              <textarea
                id="instructions"
                value={instructions}
                rows={3}
                placeholder="Scope, credentials, or constraints. Leave blank for planner auto-detect."
                onChange={(e) => setInstructions(e.target.value)}
                className="w-full resize-y rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-teal-500 focus:ring-4 focus:ring-teal-500/15 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
              />
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setShowInstructions(true)}
              className="text-sm font-medium text-teal-600 transition hover:text-teal-700 dark:text-teal-400"
            >
              + Add instructions
            </button>
          )}

          <button
            type="button"
            disabled={busy}
            onClick={submit}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-700 focus:outline-none focus:ring-4 focus:ring-teal-500/25 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy ? "Running…" : "Run tests"}
          </button>

          {error && (
            <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p>
          )}

          <div className="border-t border-slate-100 pt-3 dark:border-slate-800">
            <button
              type="button"
              onClick={() => setShowAdvanced((s) => !s)}
              className="text-xs font-medium text-slate-400 transition hover:text-slate-600 dark:hover:text-slate-300"
            >
              {showAdvanced ? "− Hide" : "+ Advanced"} · API token
            </button>
            {showAdvanced && (
              <div className="mt-2">
                <input
                  type="password"
                  value={token}
                  placeholder="x-api-key (only for token-protected servers)"
                  onChange={(e) => setToken(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 outline-none transition focus:border-teal-500 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
