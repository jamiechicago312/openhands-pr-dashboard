import { NextRequest, NextResponse } from 'next/server';
import { readFileSync } from 'fs';
import { join } from 'path';
import { PR, DashboardData } from '@/lib/types';

export const dynamic = 'force-dynamic';

const AGE_RANGES: Record<string, [number, number]> = {
  '0-24': [0, 24],
  '2-days': [0, 48],
  '3-days': [0, 72],
  '7-days': [0, 168],
  '30-days': [0, 720],
};

function loadSnapshot(): DashboardData {
  const filePath = join(process.cwd(), 'snapshot', 'dashboard.json');
  const raw = readFileSync(filePath, 'utf-8');
  return JSON.parse(raw) as DashboardData;
}

function parseDateBoundary(dateValue: string | null, endOfDay = false): number | null {
  if (!dateValue) return null;
  const isoDate = `${dateValue}T${endOfDay ? '23:59:59.999' : '00:00:00.000'}Z`;
  const timestamp = new Date(isoDate).getTime();
  return Number.isNaN(timestamp) ? null : timestamp;
}

function applyFilters(prs: PR[], params: URLSearchParams): PR[] {
  let result = prs;

  const reposParam = params.get('repos');
  if (reposParam) {
    const wanted = new Set(reposParam.split(',').map(r => r.trim()).filter(Boolean));
    result = result.filter(pr => wanted.has(pr.repo));
  }

  const labelsParam = params.get('labels');
  if (labelsParam) {
    const wanted = new Set(labelsParam.split(',').map(l => l.trim().toLowerCase()).filter(Boolean));
    result = result.filter(pr => pr.labels.some(label => wanted.has(label.toLowerCase())));
  }

  const authorType = params.get('authorType');
  if (authorType && authorType !== 'all') {
    result = result.filter(pr => pr.authorType === authorType);
  }

  const startDateBoundary = parseDateBoundary(params.get('startDate'));
  const endDateBoundary = parseDateBoundary(params.get('endDate'), true);
  if (startDateBoundary !== null || endDateBoundary !== null) {
    result = result.filter(pr => {
      const readyTime = new Date(pr.readyForReviewAt).getTime();
      if (Number.isNaN(readyTime)) return false;
      if (startDateBoundary !== null && readyTime < startDateBoundary) return false;
      if (endDateBoundary !== null && readyTime > endDateBoundary) return false;
      return true;
    });
  }

  const age = params.get('age');
  if (age && age !== 'all' && AGE_RANGES[age]) {
    const [min, max] = AGE_RANGES[age];
    result = result.filter(pr => pr.ageHours >= min && pr.ageHours < max);
  }

  const status = params.get('status');
  if (status && status !== 'all') {
    result = result.filter(pr => {
      switch (status) {
        case 'needs-review':
          return pr.needsFirstResponse || (!pr.firstReviewAt && !pr.isDraft);
        case 'changes-requested':
          return pr.reviews.some(r => r.state === 'CHANGES_REQUESTED');
        case 'approved':
          return pr.reviews.some(r => r.state === 'APPROVED');
        default:
          return true;
      }
    });
  }

  if (params.get('noReviewers') === 'true') {
    result = result.filter(pr =>
      pr.requestedReviewers.users.length === 0 && pr.requestedReviewers.teams.length === 0
    );
  }

  const reviewer = params.get('reviewer');
  if (reviewer && reviewer !== 'all') {
    result = result.filter(pr => pr.requestedReviewers.users.includes(reviewer));
  }

  const draftStatus = params.get('draftStatus');
  if (draftStatus && draftStatus !== 'all') {
    result = result.filter(pr => (draftStatus === 'drafts') === pr.isDraft);
  }

  const limit = params.get('limit');
  if (limit && limit !== 'all') {
    const n = parseInt(limit, 10);
    if (!Number.isNaN(n) && n > 0) {
      result = result.slice(0, n);
    }
  }

  return result;
}

export async function GET(request: NextRequest) {
  try {
    const snapshot = loadSnapshot();
    const params = new URL(request.url).searchParams;
    const filteredPrs = applyFilters(snapshot.prs, params);

    return NextResponse.json({
      ...snapshot,
      prs: filteredPrs,
      totalPrs: snapshot.prs.length,
      lastUpdated: snapshot.lastUpdated,
      isSnapshot: true,
    });
  } catch (error) {
    console.error('Dashboard snapshot route error:', error);
    return NextResponse.json(
      {
        error: 'Failed to load dashboard snapshot',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
