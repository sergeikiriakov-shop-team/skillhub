---
name: beliani-db-schema
description: >
  ALWAYS use before writing or changing anything that depends on the DB
  structure: SQL queries, ORM-like code, reports, imports, exports, or any
  schema-dependent logic. Do NOT guess tables, columns, indexes, constraints,
  triggers, views, routines, events, partitions, or DDL from memory or old code —
  get them from the MCP.
---

# Beliani DB schema

The source of truth for the database structure is the `beliani-db-schema` MCP, not memory or
old code.

## Workflow
1. Identify the tables/columns you need.
2. Fetch their real definition via the MCP (`get_table_schema`, `get_table_indexes`, ...).
3. Only then write the query or code.

## Reference
See `references/tools.md` for the full tool list.

## Related skills
- beliani-sql-query
- beliani-server-logs
