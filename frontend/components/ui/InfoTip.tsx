// Small "i" badge that shows a description on hover (native tooltip).
export default function InfoTip({ text }: { text: string }) {
  return (
    <span
      title={text}
      aria-label={text}
      className="inline-flex items-center justify-center w-3.5 h-3.5 ml-1 align-middle rounded-full border border-[var(--text-secondary)] text-[var(--text-secondary)] text-[9px] leading-none cursor-help select-none"
    >
      i
    </span>
  );
}
