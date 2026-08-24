"""SelfReview aggregate → DTOs.

Separated from persistence on purpose: turning a stored review into what a reader sees involves
real decisions — which commit the links point at, what counts as fixed — and those belong in one
readable place, not scattered through query code."""

from __future__ import annotations

from ...platform.config import get_settings
from ..code_links import commit_url, finding_url
from ..models import SelfReview
from ..schemas import SelfReviewFindingOut, SelfReviewFixOut, SelfReviewOut, SelfReviewSummary


def to_summary(self_review: SelfReview) -> SelfReviewSummary:
    return SelfReviewSummary(
        id=self_review.id,
        task_ref=self_review.task_ref,
        branch=self_review.branch,
        lane=self_review.lane,
        skill=self_review.skill_name,
        model=self_review.model,
        verdict=self_review.verdict,
        finding_count=len(self_review.findings or []),
        blocking_count=self_review.blocking_count,
        severity_counts=self_review.severity_counts,
        fixed_count=self_review.fixed_count,
        author=self_review.author.name if self_review.author else None,
        task_review_id=self_review.task_review_id,
        created_at=self_review.created_at,
    )


def _repo_of(self_review: SelfReview) -> str | None:
    """The repository to link against: the one the run reported, else the instance's main one — so
    runs recorded before the agent started sending its remote still link correctly."""
    return self_review.repo or get_settings().default_repo_url or None


def to_detail(self_review: SelfReview) -> SelfReviewOut:
    summary = to_summary(self_review)
    commit_shas = list(self_review.commit_shas or [])
    # Pin links to the commit the review actually read; line numbers drift on a branch. Falls back
    # to the branch when the run recorded no SHAs.
    ref = commit_shas[-1] if commit_shas else self_review.branch
    repo = _repo_of(self_review)
    template = get_settings().skillhub_code_link_template

    fixes_by_finding: dict[int, list[SelfReviewFixOut]] = {}
    for fix in self_review.fixes:
        fixes_by_finding.setdefault(fix.finding_index, []).append(
            SelfReviewFixOut(
                id=fix.id,
                finding_index=fix.finding_index,
                commit_sha=fix.commit_sha,
                note=fix.note,
                author=fix.author.name if fix.author else None,
                created_at=fix.created_at,
                commit_url=commit_url(repo, fix.commit_sha),
            )
        )

    findings = []
    for index, raw in enumerate(self_review.findings or []):
        finding = SelfReviewFindingOut(**raw)
        finding.url = finding_url(
            repo=repo, ref=ref, path=finding.file, line=finding.line, template=template
        )
        finding.fixes = fixes_by_finding.get(index, [])
        findings.append(finding)

    return SelfReviewOut(
        **summary.model_dump(),
        commit_shas=commit_shas,
        repo=self_review.repo,
        summary=self_review.summary,
        findings=findings,
    )
