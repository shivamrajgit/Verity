import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ReportViewProps {
  markdown: string;
  runId: string | null;
}

export function ReportView({ markdown, runId }: ReportViewProps) {
  const [copied, setCopied] = useState(false);

  if (!markdown) return null;

  async function copy() {
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard may be blocked; ignore */
    }
  }

  function download() {
    const blob = new Blob([markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `verity-report-${runId ?? "run"}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const btn =
    "rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800";

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-4 py-3 dark:border-slate-800">
        <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Report</h2>
        <div className="flex gap-2">
          <button type="button" onClick={copy} className={btn}>
            {copied ? "Copied ✓" : "Copy"}
          </button>
          <button type="button" onClick={download} className={btn}>
            Download .md
          </button>
        </div>
      </div>
      <div className="max-h-[32rem] overflow-y-auto px-5 py-4">
        <div className="prose prose-sm prose-slate max-w-none dark:prose-invert prose-pre:bg-slate-900 prose-pre:text-slate-100">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{markdown}</ReactMarkdown>
        </div>
      </div>
    </section>
  );
}
