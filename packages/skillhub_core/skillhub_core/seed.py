"""Import skills from a directory tree into the registry.

A skill is any immediate subdirectory containing a ``SKILL.md`` (the canonical layout used by
Prologistics' ``ai.readme/skills``). Run with ``--no-llm`` for an offline smoke test.

    python -m skillhub_core.seed --path /seed/skills --no-llm
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .db import init_db, session_scope
from .models import SOURCE_TYPE_IMPORT
from .parsing import parse_skill_dir
from .pipeline import ingest

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("skillhub.seed")


def discover_skill_dirs(root: Path) -> list[Path]:
    """Immediate subdirectories that contain a SKILL.md, sorted by name."""
    return sorted(
        (p for p in root.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()),
        key=lambda p: p.name,
    )


def run(path: str, author: str, run_llm: bool) -> int:
    root = Path(path)
    if not root.is_dir():
        logger.error("Path %s is not a directory", root)
        return 1

    init_db()
    skill_dirs = discover_skill_dirs(root)
    if not skill_dirs:
        logger.warning("No skills (subdir with SKILL.md) found under %s", root)
        return 0

    logger.info("Found %d skill(s) under %s", len(skill_dirs), root)
    for skill_dir in skill_dirs:
        parsed = parse_skill_dir(skill_dir)
        with session_scope() as session:
            result = ingest(
                session,
                parsed,
                author=author,
                source_type=SOURCE_TYPE_IMPORT,
                origin=str(skill_dir),
                run_llm=run_llm,
            )
        logger.info(
            "imported %-28s (v%s new=%s embedded=%s evaluated=%s categorized=%s) %s",
            parsed.name,
            result.version_id,
            result.is_new_version,
            result.embedded,
            result.evaluated,
            result.categorized,
            "; ".join(result.notes),
        )
    logger.info("Seed complete.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import Claude Code skills into SkillHub.")
    parser.add_argument("--path", required=True, help="Directory containing skill subfolders.")
    parser.add_argument("--author", default="prologistics", help="Author to attribute imports to.")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM evaluation/categorization.")
    args = parser.parse_args(argv)
    return run(args.path, args.author, run_llm=not args.no_llm)


if __name__ == "__main__":
    sys.exit(main())
