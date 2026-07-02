import { NextResponse } from 'next/server';
import { readFileSync } from 'fs';
import { join } from 'path';

export const dynamic = 'force-dynamic';

type Repo = {
  id: number;
  name: string;
  full_name: string;
  description: string | null;
  stargazers_count: number;
  language: string | null;
  updated_at: string;
  html_url: string;
};

type RepositoriesSnapshot = {
  repositories: Repo[];
  total: number;
  organizations: string[];
  snapshotTakenAt: string;
};

let cache: RepositoriesSnapshot | null = null;

function loadSnapshot(): RepositoriesSnapshot {
  if (cache) return cache;
  const filePath = join(process.cwd(), 'snapshot', 'repositories.json');
  const raw = readFileSync(filePath, 'utf-8');
  cache = JSON.parse(raw) as RepositoriesSnapshot;
  return cache;
}

export async function GET() {
  try {
    const data = loadSnapshot();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Repositories snapshot route error:', error);
    return NextResponse.json(
      {
        error: 'Failed to load repositories snapshot',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
