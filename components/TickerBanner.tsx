interface TickerBannerProps {
  message: string;
}

export default function TickerBanner({ message }: TickerBannerProps) {
  const repeated = `${message}   •   `;
  const content = repeated.repeat(8);

  return (
    <div
      role="status"
      aria-live="polite"
      className="sticky top-0 z-50 w-full overflow-hidden border-b border-amber-700/40 bg-amber-300 text-amber-950 shadow-sm"
    >
      <div className="flex items-center">
        <span className="flex-shrink-0 bg-amber-500 px-3 py-2 text-xs font-bold uppercase tracking-wider text-amber-950 shadow-sm">
          Snapshot
        </span>
        <div className="relative flex-1 overflow-hidden">
          <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-8 bg-gradient-to-r from-amber-300 to-transparent" />
          <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-8 bg-gradient-to-l from-amber-300 to-transparent" />
          <div className="flex w-max animate-marquee whitespace-nowrap py-2 text-sm font-medium">
            <span>{content}</span>
            <span aria-hidden="true">{content}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
