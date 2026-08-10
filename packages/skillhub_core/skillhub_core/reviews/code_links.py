"""Turning a finding into a link to the exact line it is about.

The repository is recorded per self-review, not configured globally: SkillHub serves a team that
works in more than one repo, and the agent running the review already knows which one it is in
(``git remote get-url origin``). It sends that remote; normalizing it and building the URL happens
here, so the format stays the service's business — a wrong link shape is fixed once, centrally, and
every existing finding follows, because URLs are derived at read time and never stored.

Pure functions, no DB and no framework: unit-testable on their own."""

from __future__ import annotations

import re

# scp-style git remote: git@host:owner/repo(.git)
_SCP_REMOTE = re.compile(r"^(?:[\w.-]+@)?([\w.-]+):(?!/)(.+?)(?:\.git)?/?$")
# URL-style remote: {ssh,git,http,https}://[user@]host/owner/repo(.git)
_URL_REMOTE = re.compile(r"^(?:ssh|git|https?)://(?:[^@/]+@)?([\w.-]+(?::\d+)?)/(.+?)(?:\.git)?/?$")

# Bitbucket words its blob path differently from GitHub/GitLab/Gitea, which all share /blob/.
_BITBUCKET_TEMPLATE = "{repo}/src/{ref}/{path}#lines-{line}"
_BLOB_TEMPLATE = "{repo}/blob/{ref}/{path}#L{line}"


def normalize_repo_url(raw: str | None) -> str | None:
    """A git remote in any of its usual spellings → the browsable https base, or None.

    ``git@github.com:org/repo.git`` and ``https://github.com/org/repo`` both become
    ``https://github.com/org/repo``. A local path or an unparsable string yields None rather than a
    broken link."""
    if not raw:
        return None
    remote = raw.strip()
    if not remote:
        return None
    for pattern in (_URL_REMOTE, _SCP_REMOTE):
        match = pattern.match(remote)
        if match:
            host, path = match.group(1), match.group(2).strip("/")
            return f"https://{host}/{path}" if path else None
    return None


def _template_for(repo: str) -> str:
    return _BITBUCKET_TEMPLATE if "bitbucket." in repo else _BLOB_TEMPLATE


def finding_url(
    *,
    repo: str | None,
    ref: str | None,
    path: str | None,
    line: int | None,
    template: str = "",
) -> str | None:
    """Link to ``path`` (at ``line``) as of ``ref``, or None when it cannot be located.

    ``ref`` should be the commit the review actually looked at — line numbers drift on a branch, a
    SHA does not. ``template`` overrides the host-derived shape (set it for a code browser that
    words its paths differently); it may use {repo}, {ref}, {path} and {line}. A finding with no
    file is change-wide and gets no link; with no line, the anchor is dropped rather than pointing
    at line 0."""
    if not path or not ref:
        return None
    shape = template or (_template_for(repo) if repo else "")
    if not shape:
        return None
    if line is None:
        # Anchors are the last segment in every shape here; without a line there is nothing to
        # anchor to, and "#L" / "#lines-" alone would be a dead fragment.
        shape = shape.split("#", 1)[0]
    return shape.format(repo=(repo or "").rstrip("/"), ref=ref, path=path.lstrip("/"), line=line)
