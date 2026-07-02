interface GitHubLinkProps {
  href: string;
  label?: string;
  variant?: 'ticker' | 'header';
  darkMode?: boolean;
}

export default function GitHubLink({
  href,
  label = 'View on GitHub',
  variant = 'header',
  darkMode = false,
}: GitHubLinkProps) {
  const className =
    variant === 'ticker'
      ? 'inline-flex items-center gap-1.5 bg-amber-950 px-3 py-2 text-xs font-bold uppercase tracking-wider text-amber-100 transition-colors hover:bg-amber-900 hover:text-white'
      : `inline-flex items-center gap-2 px-3 py-1.5 text-sm rounded border transition-colors ${
          darkMode
            ? 'bg-gray-800 hover:bg-gray-700 text-white border-gray-700'
            : 'bg-gray-900 hover:bg-gray-700 text-white border-gray-900'
        }`;

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={className}
      aria-label={label}
      title="Open the source repository on GitHub"
    >
      <svg
        viewBox="0 0 24 24"
        aria-hidden="true"
        className="h-4 w-4 fill-current flex-shrink-0"
      >
        <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.92.58.1.79-.25.79-.56v-2.16c-3.2.7-3.88-1.37-3.88-1.37-.52-1.33-1.28-1.69-1.28-1.69-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.28 1.18-3.08-.12-.29-.51-1.46.11-3.04 0 0 .96-.31 3.15 1.18.92-.26 1.9-.39 2.88-.39s1.96.13 2.88.39c2.19-1.49 3.15-1.18 3.15-1.18.62 1.58.23 2.75.11 3.04.73.8 1.18 1.82 1.18 3.08 0 4.42-2.69 5.39-5.26 5.68.41.36.78 1.06.78 2.13v3.16c0 .31.21.67.8.56C20.21 21.39 23.5 17.08 23.5 12 23.5 5.65 18.35.5 12 .5z" />
      </svg>
      <span>{label}</span>
    </a>
  );
}