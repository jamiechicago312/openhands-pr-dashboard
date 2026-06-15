const KNOWN_BOT_LOGINS = new Set([
  'all-hands-bot',
  'blacksmith-sh[bot]',
  'claudecode',
  'codex',
  'copilot',
  'dependabot',
  'dependabot[bot]',
  'fly-io[bot]',
  'github-actions',
  'github-actions[bot]',
  'openhands',
  'openhands-bot',
  'openhands-release-bot[bot]',
  'renovate',
  'renovate[bot]',
  'smolpaws',
]);

export function isBotLogin(login?: string | null): boolean {
  if (!login) return false;

  const normalizedLogin = login.toLowerCase();

  return KNOWN_BOT_LOGINS.has(normalizedLogin)
    || normalizedLogin.includes('[bot]')
    || normalizedLogin.endsWith('-bot')
    || normalizedLogin.endsWith('_bot');
}
