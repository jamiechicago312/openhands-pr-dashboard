#!/usr/bin/env python3
"""
Snapshot script for the OpenHands community PR dashboard.

Replicates the data layer of OpenHands/community-pr-dashboard so the snapshot
matches what the production dashboard would return at a point in time, but
without any GitHub API calls at runtime.

Outputs: snapshot/dashboard.json with the same shape that the
/app/api/dashboard Next.js route produces for the page component.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
ORG = "OpenHands"
REPO_PAGE_SIZE = 50
MAX_PR_PAGES_PER_REPO = 10
REVIEW_WINDOW_DAYS = 30
SNAPSHOT_TIMESTAMP = "2026-07-02T02:58:14Z"
MIN_REVIEWS_FOR_MEDIAN = 3

GRAPHQL_URL = "https://api.github.com/graphql"
RAW_URL_TEMPLATE = "https://raw.githubusercontent.com/OpenHands/champions-list/main/data/excluded-logins.json"

KNOWN_BOT_LOGINS = {
    "all-hands-bot",
    "blacksmith-sh[bot]",
    "claudecode",
    "codex",
    "copilot",
    "dependabot",
    "dependabot[bot]",
    "fly-io[bot]",
    "github-actions",
    "github-actions[bot]",
    "openhands",
    "openhands-bot",
    "openhands-release-bot[bot]",
    "renovate",
    "renovate[bot]",
    "smolpaws",
}


def is_bot_login(login):
    if not login:
        return False
    n = login.lower()
    return (
        n in KNOWN_BOT_LOGINS
        or "[bot]" in n
        or n.endswith("-bot")
        or n.endswith("_bot")
    )


def github_get(url):
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "snapshot-script/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def graphql(query, variables=None):
    variables = variables or {}
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "snapshot-script/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if "errors" in body and body["errors"]:
        raise RuntimeError(f"GraphQL error: {body['errors']}")
    return body["data"]


def parse_dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def get_employee_logins():
    try:
        req = urllib.request.Request(RAW_URL_TEMPLATE, headers={"User-Agent": "snapshot-script"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        data = {"logins": []}
    employees = {
        entry["login"].strip().lower()
        for entry in data.get("logins", [])
        if entry.get("reason", "").lower() == "employee or org member"
        and entry.get("login")
    }
    return employees


def get_org_members():
    members = set()
    cursor = None
    while True:
        query = """
        query ($login: String!, $cursor: String) {
          organization(login: $login) {
            membersWithRole(first: 100, after: $cursor) {
              pageInfo { hasNextPage endCursor }
              nodes { login }
            }
          }
        }
        """
        data = graphql(query, {"login": ORG, "cursor": cursor})
        conn = data["organization"]["membersWithRole"]
        members.update(n["login"].strip().lower() for n in conn["nodes"])
        if not conn["pageInfo"]["hasNextPage"]:
            break
        cursor = conn["pageInfo"]["endCursor"]
    return members


def list_active_repos():
    repos = []
    page = 1
    while True:
        data = github_get(
            f"https://api.github.com/orgs/{ORG}/repos?type=public"
            f"&per_page=100&page={page}&sort=updated"
        )
        if not data:
            break
        for repo in data:
            if not repo["archived"] and not repo["disabled"]:
                repos.append({
                    "full_name": repo["full_name"],
                    "name": repo["name"],
                    "description": repo.get("description"),
                    "stargazers_count": repo.get("stargazers_count", 0),
                    "language": repo.get("language"),
                    "updated_at": repo.get("updated_at"),
                })
        if len(data) < 100:
            break
        page += 1
    return repos


def get_repo_collaborators(owner, repo):
    collaborators = []
    page = 1
    while True:
        try:
            data = github_get(
                f"https://api.github.com/repos/{owner}/{repo}/collaborators"
                f"?affiliation=all&per_page=100&page={page}"
            )
        except Exception:
            return collaborators
        if not data:
            break
        for c in data:
            perms = c.get("permissions", {})
            if perms.get("admin") or perms.get("maintain") or perms.get("push"):
                collaborators.append(c["login"])
        if len(data) < 100:
            break
        page += 1
    return collaborators


MAINTAINER_ALLOWLIST = {
    "malhotra5", "rbren", "xingyaoww", "neubig", "csmith49",
    "hieptl", "enyst", "mamoodi", "li-boxuan", "jpshackelford", "tobitege",
}
EMPLOYEE_ALLOWLIST = set()
EMPLOYEE_DENYLIST = set()
MAINTAINER_DENYLIST = set()


def fetch_open_prs(owner, repo):
    prs = []
    cursor = None
    page_count = 0
    while page_count < MAX_PR_PAGES_PER_REPO:
        query = """
        query OpenPRs($owner: String!, $name: String!, $cursor: String) {
          repository(owner: $owner, name: $name) {
            pullRequests(states: OPEN, first: 50, after: $cursor, orderBy: {field: CREATED_AT, direction: DESC}) {
              pageInfo { hasNextPage endCursor }
              nodes {
                number title url createdAt updatedAt isDraft authorAssociation state
                author { login }
                mergeable
                labels(first: 20) { nodes { name } }
                reviewRequests(first: 20) {
                  nodes {
                    requestedReviewer {
                      __typename
                      ... on User { login }
                      ... on Team { slug }
                    }
                  }
                }
                reviews(first: 50) {
                  nodes {
                    author { login }
                    state
                    submittedAt
                  }
                }
                timelineItems(first: 10, itemTypes: [READY_FOR_REVIEW_EVENT]) {
                  nodes {
                    __typename
                    ... on ReadyForReviewEvent { createdAt }
                  }
                }
              }
            }
          }
        }
        """
        data = graphql(query, {"owner": owner, "name": repo, "cursor": cursor})
        conn = data["repository"]["pullRequests"]
        for pr in conn["nodes"]:
            if pr["state"] == "OPEN":
                prs.append(pr)
        if not conn["pageInfo"]["hasNextPage"]:
            break
        cursor = conn["pageInfo"]["endCursor"]
        page_count += 1
    return prs


def fetch_merged_prs_with_reviews(owner, repo, since):
    completed = []
    requests = []
    cursor = None
    page_count = 0
    while page_count < 5:
        query = """
        query RecentMergedPRs($owner: String!, $name: String!, $cursor: String) {
          repository(owner: $owner, name: $name) {
            pullRequests(states: MERGED, first: 50, after: $cursor, orderBy: {field: UPDATED_AT, direction: DESC}) {
              pageInfo { hasNextPage endCursor }
              nodes {
                number url mergedAt
                timelineItems(first: 100, itemTypes: [REVIEW_REQUESTED_EVENT, PULL_REQUEST_REVIEW]) {
                  nodes {
                    __typename
                    ... on ReviewRequestedEvent {
                      createdAt
                      requestedReviewer {
                        __typename
                        ... on User { login }
                      }
                    }
                    ... on PullRequestReview {
                      author { login }
                      authorAssociation
                      submittedAt
                      state
                    }
                  }
                }
              }
            }
          }
        }
        """
        data = graphql(query, {"owner": owner, "name": repo, "cursor": cursor})
        conn = data["repository"]["pullRequests"]
        stop = False
        for pr in conn["nodes"]:
            if pr.get("mergedAt") and parse_dt(pr["mergedAt"]) < since:
                stop = True
                break

            pr_requests = {}
            reviews = []
            for item in pr["timelineItems"]["nodes"]:
                if item["__typename"] == "ReviewRequestedEvent" and item.get("requestedReviewer", {}).get("login"):
                    login = item["requestedReviewer"]["login"]
                    if is_bot_login(login):
                        continue
                    if login not in pr_requests:
                        pr_requests[login] = item["createdAt"]
                elif item["__typename"] == "PullRequestReview" and item.get("author", {}).get("login") and item.get("submittedAt"):
                    login = item["author"]["login"]
                    if is_bot_login(login):
                        continue
                    if item["state"] in ("APPROVED", "CHANGES_REQUESTED", "COMMENTED"):
                        reviews.append({
                            "login": login,
                            "authorAssociation": item.get("authorAssociation", "NONE"),
                            "submittedAt": item["submittedAt"],
                        })

            for login, requested_at in pr_requests.items():
                if parse_dt(requested_at) >= since:
                    requests.append({
                        "reviewerLogin": login,
                        "requestedAt": requested_at,
                        "prNumber": pr["number"],
                    })

            fulfilled = set()
            for review in reviews:
                if parse_dt(review["submittedAt"]) < since:
                    continue
                req_at = pr_requests.get(review["login"])
                req_in_range = req_at and parse_dt(req_at) >= since
                review_after = req_in_range and parse_dt(review["submittedAt"]) >= parse_dt(req_at)
                is_first = bool(review_after and review["login"] not in fulfilled)
                if is_first:
                    fulfilled.add(review["login"])
                completed.append({
                    "reviewerLogin": review["login"],
                    "authorAssociation": review["authorAssociation"],
                    "submittedAt": review["submittedAt"],
                    "requestedAt": req_at if is_first else None,
                    "prNumber": pr["number"],
                    "prUrl": pr["url"],
                })

        if stop or not conn["pageInfo"]["hasNextPage"]:
            break
        cursor = conn["pageInfo"]["endCursor"]
        page_count += 1
    return {"completedReviews": completed, "reviewRequests": requests}


def fetch_all_merged_pr_review_stats(owner, repo, since, employees):
    community = []
    org_member = []
    bot = []
    cursor = None
    page_count = 0
    while page_count < 5:
        query = """
        query AllMergedPRReviews($owner: String!, $name: String!, $cursor: String) {
          repository(owner: $owner, name: $name) {
            pullRequests(states: MERGED, first: 50, after: $cursor, orderBy: {field: UPDATED_AT, direction: DESC}) {
              pageInfo { hasNextPage endCursor }
              nodes {
                number url createdAt mergedAt isDraft
                author { login }
                authorAssociation
                timelineItems(first: 100, itemTypes: [READY_FOR_REVIEW_EVENT, PULL_REQUEST_REVIEW]) {
                  nodes {
                    __typename
                    ... on ReadyForReviewEvent { createdAt }
                    ... on PullRequestReview {
                      author { login }
                      authorAssociation
                      submittedAt
                      state
                    }
                  }
                }
              }
            }
          }
        }
        """
        data = graphql(query, {"owner": owner, "name": repo, "cursor": cursor})
        conn = data["repository"]["pullRequests"]
        stop = False
        for pr in conn["nodes"]:
            if pr.get("mergedAt") and parse_dt(pr["mergedAt"]) < since:
                stop = True
                break
            author = (pr.get("author") or {}).get("login")
            if not author:
                continue
            assoc = pr.get("authorAssociation") or "NONE"
            is_bot = is_bot_login(author)
            is_emp = author.lower() in employees
            has_write = assoc in ("COLLABORATOR", "MEMBER", "OWNER")

            ready_at = None
            first_reviews = {}
            for item in pr["timelineItems"]["nodes"]:
                if item["__typename"] == "ReadyForReviewEvent" and ready_at is None:
                    ready_at = item["createdAt"]
                elif item["__typename"] == "PullRequestReview":
                    a = (item.get("author") or {}).get("login")
                    if a and item.get("submittedAt") and not is_bot_login(a):
                        if item["state"] in ("APPROVED", "CHANGES_REQUESTED", "COMMENTED"):
                            if a not in first_reviews:
                                first_reviews[a] = item["submittedAt"]
            if not ready_at:
                ready_at = pr["createdAt"]
            ready_ts = parse_dt(ready_at).timestamp()

            for reviewer, first_review_at in first_reviews.items():
                review_ts = parse_dt(first_review_at).timestamp()
                hours = (review_ts - ready_ts) / 3600.0
                if hours <= 0:
                    continue
                if parse_dt(first_review_at) < since:
                    continue
                entry = {
                    "reviewerLogin": reviewer,
                    "prNumber": pr["number"],
                    "prUrl": pr["url"],
                    "prAuthor": author,
                    "readyForReviewAt": ready_at,
                    "firstReviewAt": first_review_at,
                    "reviewTimeHours": hours,
                }
                if is_bot:
                    bot.append(entry)
                elif is_emp or has_write:
                    org_member.append({**entry, "prAuthorAssociation": assoc})
                else:
                    community.append({**entry, "prAuthorAssociation": assoc})

        if stop or not conn["pageInfo"]["hasNextPage"]:
            break
        cursor = conn["pageInfo"]["endCursor"]
        page_count += 1
    return {
        "communityReviews": community,
        "orgMemberReviews": org_member,
        "botReviews": bot,
    }


def is_employee(login, employees):
    return login.lower() in employees


def is_org_member_assoc(assoc):
    return assoc in ("MEMBER", "OWNER")


def get_author_type(login, employees, assoc, maintainers, collaborators):
    if is_bot_login(login):
        return "bot"
    if login in maintainers:
        return "maintainer"
    if is_employee(login, employees) or is_org_member_assoc(assoc):
        return "employee"
    if login in collaborators or assoc == "COLLABORATOR":
        return "collaborator"
    return "community"


def compute_firsts(raw_pr, employees):
    reviews = [r for r in raw_pr["reviews"]["nodes"] if r.get("submittedAt") and (r.get("author") or {}).get("login") and not is_bot_login((r.get("author") or {}).get("login"))]
    reviews.sort(key=lambda r: r["submittedAt"])
    first_review_at = reviews[0]["submittedAt"] if reviews else None
    first_employee = next((r for r in reviews if is_employee((r["author"] or {}).get("login", ""), employees)), None)
    first_response_at = first_employee["submittedAt"] if first_employee else None
    return first_response_at, first_review_at


def transform_pr(raw_pr, employees, maintainers, collaborators):
    first_response_at, first_review_at = compute_firsts(raw_pr, employees)
    created_at = raw_pr["createdAt"]
    age_hours = (parse_dt(SNAPSHOT_TIMESTAMP).timestamp() -
                 parse_dt(created_at).timestamp()) / 3600.0
    needs_first_response = not first_response_at
    overdue_first_response = needs_first_response and age_hours > 72
    overdue_first_review = not first_review_at and age_hours > 144

    requested_reviewers = {
        "users": [
            r["requestedReviewer"]["login"]
            for r in raw_pr["reviewRequests"]["nodes"]
            if r["requestedReviewer"]["__typename"] == "User" and not is_bot_login(r["requestedReviewer"]["login"])
        ],
        "teams": [
            r["requestedReviewer"]["slug"]
            for r in raw_pr["reviewRequests"]["nodes"]
            if r["requestedReviewer"]["__typename"] == "Team"
        ],
    }

    reviews = [
        {
            "authorLogin": (r["author"] or {}).get("login") or "unknown",
            "state": r["state"],
            "submittedAt": r["submittedAt"],
        }
        for r in raw_pr["reviews"]["nodes"]
    ]

    ready_event = next((it for it in raw_pr["timelineItems"]["nodes"] if it["__typename"] == "ReadyForReviewEvent"), None)
    ready_for_review_at = ready_event["createdAt"] if ready_event else raw_pr["createdAt"]

    login = (raw_pr["author"] or {}).get("login") or "unknown"
    assoc = raw_pr["authorAssociation"]

    return {
        "repo": f"{raw_pr['repository']['owner']['login']}/{raw_pr['repository']['name']}",
        "number": raw_pr["number"],
        "title": raw_pr["title"],
        "url": raw_pr["url"],
        "authorLogin": login,
        "authorAssociation": assoc,
        "authorType": get_author_type(login, employees, assoc, maintainers, collaborators),
        "isEmployeeAuthor": is_employee(login, employees) or is_org_member_assoc(assoc),
        "isDraft": raw_pr["isDraft"],
        "createdAt": raw_pr["createdAt"],
        "updatedAt": raw_pr["updatedAt"],
        "readyForReviewAt": ready_for_review_at,
        "labels": [l["name"] for l in raw_pr["labels"]["nodes"]],
        "requestedReviewers": requested_reviewers,
        "reviews": reviews,
        "firstHumanResponseAt": first_response_at,
        "firstReviewAt": first_review_at,
        "ageHours": round(age_hours, 1),
        "needsFirstResponse": needs_first_response,
        "overdueFirstResponse": overdue_first_response,
        "overdueFirstReview": overdue_first_review,
    }


def median(values, min_count=0):
    if len(values) == 0 or len(values) < min_count:
        return None
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        return (s[mid - 1] + s[mid]) / 2.0
    return s[mid]


def format_time(hours):
    if hours is None:
        return "N/A"
    if hours < 24:
        return f"{int(round(hours))}h"
    return f"{int(round(hours / 24))}d"


def compute_reviewer_stats(prs, review_stats, employees):
    completed = review_stats["completedReviews"]
    reqs = review_stats["reviewRequests"]
    maintainers = set()
    for pr in prs:
        if pr["authorType"] == "maintainer":
            maintainers.add(pr["authorLogin"])
    for r in completed:
        if is_bot_login(r["reviewerLogin"]):
            continue
        if r["authorAssociation"] in ("COLLABORATOR", "MEMBER", "OWNER"):
            maintainers.add(r["reviewerLogin"])

    pending = {}
    for pr in prs:
        for reviewer in pr["requestedReviewers"]["users"]:
            if is_bot_login(reviewer):
                continue
            pending[reviewer] = pending.get(reviewer, 0) + 1

    stats = {}
    for r in completed:
        login = r["reviewerLogin"]
        if is_bot_login(login):
            continue
        if login not in stats:
            stats[login] = {"completedTotal": 0, "completedRequested": 0,
                            "completedUnrequested": 0, "reviewTimes": []}
        stats[login]["completedTotal"] += 1
        if r["requestedAt"]:
            stats[login]["completedRequested"] += 1
            rt = (parse_dt(r["submittedAt"]).timestamp() -
                  parse_dt(r["requestedAt"]).timestamp()) / 3600.0
            if rt > 0:
                stats[login]["reviewTimes"].append(rt)
        else:
            stats[login]["completedUnrequested"] += 1

    req_stats = {}
    for req in reqs:
        login = req["reviewerLogin"]
        if is_bot_login(login):
            continue
        req_stats[login] = req_stats.get(login, 0) + 1

    all_logins = set(pending) | set(stats) | set(req_stats)
    filtered = [l for l in all_logins if not is_bot_login(l) and (is_employee(l, employees) or l in maintainers)]

    reviewers = []
    for login in filtered:
        s = stats.get(login, {"completedTotal": 0, "completedRequested": 0, "completedUnrequested": 0, "reviewTimes": []})
        requested_total = req_stats.get(login, 0)
        pending_count = pending.get(login, 0)
        completion_rate = (s["completedRequested"] / requested_total * 100) if requested_total > 0 else None
        reviewers.append({
            "name": login,
            "pendingCount": pending_count,
            "completedTotal": s["completedTotal"],
            "completedRequested": s["completedRequested"],
            "completedUnrequested": s["completedUnrequested"],
            "requestedTotal": requested_total,
            "completionRate": completion_rate,
            "medianReviewTimeHours": median(s["reviewTimes"]),
        })

    reviewers.sort(key=lambda r: r["completedTotal"], reverse=True)
    return reviewers


def _grouped_reviewer_stats(reviews):
    grouped = {}
    for r in reviews:
        if r["reviewTimeHours"] <= 0:
            continue
        grouped.setdefault(r["reviewerLogin"], []).append(r["reviewTimeHours"])
    return grouped


def compute_community_reviewer_stats(reviews):
    grouped = _grouped_reviewer_stats(reviews)
    out = [
        {"name": login,
         "communityPRsReviewed": len(times),
         "medianCommunityReviewTimeHours": median(times, MIN_REVIEWS_FOR_MEDIAN)}
        for login, times in grouped.items()
    ]
    out.sort(key=lambda x: x["communityPRsReviewed"], reverse=True)
    return out


def compute_org_member_reviewer_stats(reviews):
    grouped = _grouped_reviewer_stats(reviews)
    out = [
        {"name": login,
         "orgMemberPRsReviewed": len(times),
         "medianOrgMemberReviewTimeHours": median(times, MIN_REVIEWS_FOR_MEDIAN)}
        for login, times in grouped.items()
    ]
    out.sort(key=lambda x: x["orgMemberPRsReviewed"], reverse=True)
    return out


def compute_bot_reviewer_stats(reviews):
    grouped = _grouped_reviewer_stats(reviews)
    out = [
        {"name": login,
         "botPRsReviewed": len(times),
         "medianBotReviewTimeHours": median(times, MIN_REVIEWS_FOR_MEDIAN)}
        for login, times in grouped.items()
    ]
    out.sort(key=lambda x: x["botPRsReviewed"], reverse=True)
    return out


def compute_dashboard(prs, employees, review_stats, community_reviews, org_member_reviews, bot_reviews):
    community_prs = [pr for pr in prs if pr["authorType"] == "community"]
    non_draft_prs = [pr for pr in prs if not pr["isDraft"]]

    tffr_times = [
        (parse_dt(pr["firstHumanResponseAt"]).timestamp() -
         parse_dt(pr["readyForReviewAt"]).timestamp()) / 3600.0
        for pr in community_prs if pr["firstHumanResponseAt"]
    ]
    ttfr_times = [
        (parse_dt(pr["firstReviewAt"]).timestamp() -
         parse_dt(pr["readyForReviewAt"]).timestamp()) / 3600.0
        for pr in community_prs if pr["firstReviewAt"]
    ]
    tffr_times = [t for t in tffr_times if t >= 0]
    ttfr_times = [t for t in ttfr_times if t >= 0]

    reviewers = compute_reviewer_stats(prs, review_stats, employees)

    community_stats_map = {s["name"]: s for s in compute_community_reviewer_stats(community_reviews)}
    org_stats_map = {s["name"]: s for s in compute_org_member_reviewer_stats(org_member_reviews)}
    bot_stats_map = {s["name"]: s for s in compute_bot_reviewer_stats(bot_reviews)}

    for r in reviewers:
        cs = community_stats_map.get(r["name"])
        if cs:
            r["communityPRsReviewed"] = cs["communityPRsReviewed"]
            r["medianCommunityReviewTimeHours"] = cs["medianCommunityReviewTimeHours"]
        os_ = org_stats_map.get(r["name"])
        if os_:
            r["orgMemberPRsReviewed"] = os_["orgMemberPRsReviewed"]
            r["medianOrgMemberReviewTimeHours"] = os_["medianOrgMemberReviewTimeHours"]
        bs = bot_stats_map.get(r["name"])
        if bs:
            r["botPRsReviewed"] = bs["botPRsReviewed"]
            r["medianBotReviewTimeHours"] = bs["medianBotReviewTimeHours"]

    known = {r["name"] for r in reviewers}
    for name in set(community_stats_map) | set(org_stats_map) | set(bot_stats_map):
        if name in known:
            continue
        cs = community_stats_map.get(name)
        os_ = org_stats_map.get(name)
        bs = bot_stats_map.get(name)
        reviewers.append({
            "name": name,
            "pendingCount": 0,
            "completedTotal": 0,
            "completedRequested": 0,
            "completedUnrequested": 0,
            "requestedTotal": 0,
            "completionRate": None,
            "communityPRsReviewed": cs["communityPRsReviewed"] if cs else None,
            "medianCommunityReviewTimeHours": cs["medianCommunityReviewTimeHours"] if cs else None,
            "orgMemberPRsReviewed": os_["orgMemberPRsReviewed"] if os_ else None,
            "medianOrgMemberReviewTimeHours": os_["medianOrgMemberReviewTimeHours"] if os_ else None,
            "botPRsReviewed": bs["botPRsReviewed"] if bs else None,
            "medianBotReviewTimeHours": bs["medianBotReviewTimeHours"] if bs else None,
        })

    prs_with_reviewers = [pr for pr in non_draft_prs if pr["requestedReviewers"]["users"]]
    compliance = (len(prs_with_reviewers) / len(non_draft_prs) * 100) if non_draft_prs else 0
    prs_without = [pr for pr in non_draft_prs if not pr["requestedReviewers"]["users"]]
    total_pending = sum(r["pendingCount"] for r in reviewers)
    active_reviewers = sum(1 for r in reviewers if r["pendingCount"] > 0 or r["completedTotal"] > 0)

    return {
        "kpis": {
            "openCommunityPrs": len(community_prs),
            "communityPrPercentage": f"{int(round(len(community_prs) / len(prs) * 100))}%" if prs else "0%",
            "medianResponseTime": format_time(median(tffr_times)),
            "medianReviewTime": format_time(median(ttfr_times)),
            "reviewerCompliance": f"{int(round(compliance))}%",
            "pendingReviews": total_pending,
            "activeReviewers": active_reviewers,
            "prsWithoutReviewers": len(prs_without),
        },
        "prs": prs,
        "reviewers": reviewers,
        "lastUpdated": SNAPSHOT_TIMESTAMP,
        "totalPrs": len(prs),
        "employeeCount": len(employees),
    }


def main():
    employees = get_employee_logins()
    if not employees:
        print("champions-list not available, falling back to org members", file=sys.stderr)
        employees = get_org_members()
    employees = (employees | {x.lower() for x in EMPLOYEE_ALLOWLIST}) - {x.lower() for x in EMPLOYEE_DENYLIST}
    maintainers = {x for x in MAINTAINER_ALLOWLIST} - {x for x in MAINTAINER_DENYLIST}
    print(f"employee count: {len(employees)}", file=sys.stderr)

    repos = list_active_repos()
    print(f"active repos: {len(repos)}", file=sys.stderr)

    since = parse_dt(SNAPSHOT_TIMESTAMP) - timedelta(days=REVIEW_WINDOW_DAYS)

    all_prs = []
    all_review_stats = {"completedReviews": [], "reviewRequests": []}
    all_community = []
    all_org = []
    all_bot = []

    for repo_meta in repos:
        full_name = repo_meta["full_name"]
        owner, repo = full_name.split("/", 1)
        print(f"  - {full_name}", file=sys.stderr)
        collaborators = set(get_repo_collaborators(owner, repo))
        try:
            raw_open = fetch_open_prs(owner, repo)
            for pr in raw_open:
                pr["repository"] = {"owner": {"login": owner}, "name": repo}
                all_prs.append(transform_pr(pr, employees, maintainers, collaborators))
        except Exception as e:
            print(f"    open prs failed: {e}", file=sys.stderr)
        try:
            stats = fetch_merged_prs_with_reviews(owner, repo, since)
            all_review_stats["completedReviews"].extend(stats["completedReviews"])
            all_review_stats["reviewRequests"].extend(stats["reviewRequests"])
        except Exception as e:
            print(f"    merged reviews failed: {e}", file=sys.stderr)
        try:
            all_stats = fetch_all_merged_pr_review_stats(owner, repo, since, employees)
            all_community.extend(all_stats["communityReviews"])
            all_org.extend(all_stats["orgMemberReviews"])
            all_bot.extend(all_stats["botReviews"])
        except Exception as e:
            print(f"    all-review stats failed: {e}", file=sys.stderr)

    dashboard = compute_dashboard(
        all_prs, employees, all_review_stats, all_community, all_org, all_bot
    )

    out_path = Path(__file__).resolve().parents[1] / "snapshot" / "dashboard.json"
    out_path.write_text(json.dumps(dashboard, indent=2, sort_keys=False))
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)", file=sys.stderr)
    print(f"open PRs: {len(all_prs)}; reviewers: {len(dashboard['reviewers'])}", file=sys.stderr)

    repos_path = Path(__file__).resolve().parents[1] / "snapshot" / "repositories.json"
    repos_payload = {
        "repositories": sorted(
            [
                {
                    "id": idx,
                    "name": r["name"],
                    "full_name": r["full_name"],
                    "description": r.get("description"),
                    "stargazers_count": r.get("stargazers_count", 0),
                    "language": r.get("language"),
                    "updated_at": r.get("updated_at"),
                    "html_url": f"https://github.com/{r['full_name']}",
                }
                for idx, r in enumerate(repos, start=1)
            ],
            key=lambda r: r.get("stargazers_count", 0),
            reverse=True,
        ),
        "total": len(repos),
        "organizations": [ORG],
        "snapshotTakenAt": SNAPSHOT_TIMESTAMP,
    }
    repos_path.write_text(json.dumps(repos_payload, indent=2))
    print(f"wrote {repos_path} ({repos_path.stat().st_size} bytes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
