"""Reserved for background jobs.

The service no longer runs the LLM itself — evaluation/categorization are produced by
Claude Code and submitted via POST /api/skills/{id}/assessment, so there is nothing to
schedule here at the moment. Kept as a placeholder for future non-LLM background work
(e.g. re-embedding on model change)."""
