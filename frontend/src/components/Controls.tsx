interface ControlsProps {
  onStop: () => void;
}

export function Controls({ onStop }: ControlsProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={onStop}
        className="rounded-lg bg-[#3e3a37] px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-stone-800 dark:bg-stone-100 dark:text-stone-950 dark:hover:bg-white"
      >
        Stop run
      </button>
    </div>
  );
}
