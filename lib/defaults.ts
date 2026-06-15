import { cache } from './cache';
import { config } from './config';
import { getAllRepositoriesFromOrgs } from './github';

export const FALLBACK_REPOS = [
  'OpenHands/OpenHands',
  'OpenHands/community-pr-dashboard',
  'OpenHands/docs',
  'OpenHands/benchmarks',
  'OpenHands/OpenHands-CLI',
];

function normalizeRepo(repo: string): string {
  return repo.trim().toLowerCase();
}

function filterExcludedRepos(repos: string[]): string[] {
  if (config.repos.exclude.length === 0) {
    return repos;
  }

  const excludedRepos = new Set(config.repos.exclude.map(normalizeRepo));
  return repos.filter(repo => !excludedRepos.has(normalizeRepo(repo)));
}

export async function getDefaultRepos(): Promise<string[]> {
  const cacheKey = `default-repos:${JSON.stringify({
    orgs: config.orgs,
    include: config.repos.include,
    exclude: config.repos.exclude,
  })}`;

  return cache.withCache(cacheKey, config.cache.ttlSeconds, async () => {
    if (config.repos.include.length > 0) {
      return config.repos.include;
    }

    const discoveredRepos = filterExcludedRepos(await getAllRepositoriesFromOrgs(config.orgs));
    return discoveredRepos.length > 0 ? discoveredRepos : FALLBACK_REPOS;
  });
}
