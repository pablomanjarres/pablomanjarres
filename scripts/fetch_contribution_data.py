#!/usr/bin/env python3
"""Fetch public-safe aggregates without saving repository identities or credentials.

Authentication uses GH_TOKEN/GITHUB_TOKEN or gh's existing account. Restricted
activity is kept as a separate count and never relabeled as commits. Language
counts cover visible commit groups; stars/forks cover public owned repositories.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from contribution_data import nonnegative_integer, parse_snapshot, require_complete

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "profile-3d-contrib/contribution-data.json"
REQUEST_TIMEOUT = 45
MAX_REPOSITORY_PAGES = 20

COLLECTION_FIELDS = """
login
contributionsCollection%s {
  startedAt endedAt restrictedContributionsCount
  totalCommitContributions totalIssueContributions
  totalPullRequestContributions totalPullRequestReviewContributions
  totalRepositoryContributions
  contributionCalendar {
    totalContributions
    weeks { contributionDays { date contributionCount } }
  }
  commitContributionsByRepository(maxRepositories: 100) {
    contributions { totalCount }
    repository { primaryLanguage { name } }
  }
}
"""
REPOSITORY_FIELDS = """
repositories(first: 100, after: $after, ownerAffiliations: OWNER, privacy: PUBLIC) {
  nodes { stargazerCount forkCount }
  pageInfo { hasNextPage endCursor }
}
"""


def graphql(query: str, variables: dict) -> dict:
    """Keep the API response in memory and suppress unsanitized error bodies."""
    try:
        result = subprocess.run(
            ["gh", "api", "graphql", "--hostname", "github.com", "--input", "-"],
            input=json.dumps({"query": query, "variables": variables}),
            text=True, capture_output=True, timeout=REQUEST_TIMEOUT, check=False,
        )
    except FileNotFoundError as error:
        raise ValueError("GitHub CLI is required for authenticated contribution fetching") from error
    except subprocess.TimeoutExpired as error:
        raise ValueError("GitHub GraphQL request timed out") from error
    if result.returncode:
        raise ValueError(f"GitHub GraphQL request failed (exit {result.returncode})")
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("GitHub GraphQL returned an invalid response") from error
    if response.get("errors") or not isinstance(response.get("data"), dict):
        raise ValueError("GitHub GraphQL did not return a complete result")
    return response["data"]


def profile_query(fields: str, username: str | None, definitions: tuple[str, ...] = ()) -> str:
    declarations = (["$username: String!"] if username else []) + list(definitions)
    arguments = f"({', '.join(declarations)})" if declarations else ""
    profile = "user(login: $username)" if username else "viewer"
    return f"query{arguments} {{ profile: {profile} {{ {fields} }} }}"


def fetch_snapshot(username: str | None = None, from_time: str | None = None,
                   to_time: str | None = None) -> dict:
    if bool(from_time) != bool(to_time):
        raise ValueError("Provide both --from and --to, or omit both for the current profile window")
    variables = {"username": username} if username else {}
    definitions = ()
    collection_arguments = ""
    if from_time:
        start = datetime.fromisoformat(from_time.replace("Z", "+00:00"))
        end = datetime.fromisoformat(to_time.replace("Z", "+00:00"))
        if start.tzinfo is None or end.tzinfo is None or start >= end:
            raise ValueError("--from and --to must be ordered timestamps with a timezone")
        variables.update({"from": from_time, "to": to_time})
        definitions = ("$from: DateTime!", "$to: DateTime!")
        collection_arguments = "(from: $from, to: $to)"
    fields = COLLECTION_FIELDS % collection_arguments
    profile = graphql(profile_query(fields, username, definitions), variables).get("profile")
    if not isinstance(profile, dict):
        raise ValueError("GitHub profile is unavailable to the authenticated account")
    collection = profile["contributionsCollection"]
    calendar = collection["contributionCalendar"]
    days = [{"date": day["date"], "count": day["contributionCount"]}
            for week in calendar["weeks"] for day in week["contributionDays"]]
    if not days:
        raise ValueError("GitHub returned an empty contribution calendar")
    languages = {}
    for group in collection["commitContributionsByRepository"]:
        language = group["repository"]["primaryLanguage"]
        label = language["name"] if language else "other"
        count = nonnegative_integer(group["contributions"]["totalCount"], "language count")
        languages[label] = languages.get(label, 0) + count
    stars = forks = 0
    after = None
    for page_index in range(MAX_REPOSITORY_PAGES):
        page_variables = {"after": after, **({"username": username} if username else {})}
        page = graphql(profile_query(REPOSITORY_FIELDS, username, ("$after: String",)),
                       page_variables)["profile"]["repositories"]
        for repo in page["nodes"]:
            stars += nonnegative_integer(repo["stargazerCount"], "star count")
            forks += nonnegative_integer(repo["forkCount"], "fork count")
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
        if not cursor or cursor == after:
            raise ValueError("GitHub public repository pagination did not advance")
        after = cursor
    else:
        raise ValueError(f"Public repository aggregation exceeded {MAX_REPOSITORY_PAGES} pages")
    snapshot = {
        "schema_version": 1,
        "username": profile["login"],
        "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "window": {"started_at": collection["startedAt"], "ended_at": collection["endedAt"]},
        "start": days[0]["date"], "end": days[-1]["date"],
        "contributions": calendar["totalContributions"],
        "restricted_contributions": collection["restrictedContributionsCount"],
        "activity": {
            "Commit": collection["totalCommitContributions"],
            "Issue": collection["totalIssueContributions"],
            "PullReq": collection["totalPullRequestContributions"],
            "Review": collection["totalPullRequestReviewContributions"],
            "Repo": collection["totalRepositoryContributions"],
        },
        "languages": dict(sorted(languages.items(), key=lambda item: (-item[1], item[0]))),
        "stars": stars, "forks": forks,
        "daily_contributions": days,
        "activity_scope": "visible_contribution_breakdown",
        "language_scope": "visible_commits_by_primary_language",
        "community_scope": "public_owned_repositories",
    }
    parse_snapshot(snapshot)
    return snapshot


def write_snapshot(snapshot: dict, output: Path, require_complete_breakdown: bool = False) -> None:
    data = parse_snapshot(snapshot)
    if require_complete_breakdown:
        require_complete(data)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                         prefix=f".{output.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(snapshot, stream, separators=(",", ":"), ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--username", help="Profile login; defaults to the authenticated viewer")
    parser.add_argument("--from", dest="from_time", help="Inclusive ISO timestamp with timezone")
    parser.add_argument("--to", dest="to_time", help="End ISO timestamp with timezone")
    parser.add_argument("--require-complete", action="store_true",
                        help="Fail before replacement if private activity remains untyped or language totals are incomplete")
    args = parser.parse_args()
    try:
        snapshot = fetch_snapshot(args.username, args.from_time, args.to_time)
        write_snapshot(snapshot, args.output, args.require_complete)
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f"Contribution refresh failed: {error}", file=sys.stderr)
        return 1
    print(f"Saved {len(snapshot['daily_contributions'])} days, "
          f"{snapshot['contributions']:,} total contributions, and "
          f"{snapshot['restricted_contributions']:,} restricted contributions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
