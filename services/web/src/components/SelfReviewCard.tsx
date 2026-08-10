import { Anchor, Badge, Button, Card, Code, Collapse, Group, Paper, Stack, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { SelfReviewFinding, SelfReviewSummary } from "../api";
import { useI18n } from "../i18n";

const SEVERITY_COLOR: Record<string, string> = {
  blocker: "red",
  major: "orange",
  minor: "yellow",
  nit: "gray",
};

const SEVERITY_ORDER = ["blocker", "major", "minor", "nit"];

const VERDICT_COLOR: Record<string, string> = { pass: "green", changes_needed: "orange" };

function Finding({ f }: { f: SelfReviewFinding }) {
  const { t } = useI18n();
  return (
    <Paper withBorder radius="md" p="sm">
      <Group gap="xs" wrap="nowrap" mb={f.detail || f.suggestion ? "xs" : 0} align="flex-start">
        <Badge size="sm" color={SEVERITY_COLOR[f.severity] ?? "gray"} variant="light">
          {t(`selfReview.severity.${f.severity}`)}
        </Badge>
        <Text size="sm" fw={600} style={{ flex: 1 }}>
          {f.title}
        </Text>
        {f.file && (
          <Code>
            {f.file}
            {f.line ? `:${f.line}` : ""}
          </Code>
        )}
      </Group>
      {f.detail && (
        <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
          {f.detail}
        </Text>
      )}
      {f.suggestion && (
        <Text size="sm" c="dimmed" mt={4} style={{ whiteSpace: "pre-wrap" }}>
          {t("selfReview.suggestion")}: {f.suggestion}
        </Text>
      )}
    </Paper>
  );
}

/** One self-review: what the team's review skill found in the author's own change, before anyone
 * else saw it. The summary is cheap and comes with the list; the findings are the heavy half and
 * are fetched separately — in a list (`collapsible`) only once the reader expands the card.
 * `showTask` adds the pointer fields, which are redundant on a peer review's own page. */
export default function SelfReviewCard({
  sr,
  collapsible = false,
  showTask = false,
}: {
  sr: SelfReviewSummary;
  collapsible?: boolean;
  showTask?: boolean;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(!collapsible);
  const { data } = useQuery({
    queryKey: ["selfReview", sr.id],
    queryFn: () => api.getSelfReview(sr.id),
    enabled: open,
  });
  const findings = data?.findings ?? [];

  return (
    <Card withBorder radius="md" padding="md">
      <Group justify="space-between" wrap="nowrap" mb="xs">
        <Group gap="xs" wrap="nowrap">
          <Badge color={VERDICT_COLOR[sr.verdict] ?? "gray"} variant="light">
            {t(`selfReview.verdict.${sr.verdict}`)}
          </Badge>
          <Text size="sm" fw={600}>
            {sr.skill || "—"}
          </Text>
          {sr.model && (
            <Text size="xs" c="dimmed">
              {sr.model}
            </Text>
          )}
        </Group>
        <Text size="xs" c="dimmed">
          {new Date(sr.created_at).toLocaleString()}
        </Text>
      </Group>

      {showTask && (
        <Group gap="xs" mb={4} wrap="wrap">
          <Text size="xs" c="dimmed">
            {t("reviews.task")}: {sr.task_ref}
          </Text>
          {sr.branch && (
            <Text size="xs" c="dimmed">
              · {sr.branch}
            </Text>
          )}
          {sr.author && (
            <Text size="xs" c="dimmed">
              · {t("reviews.by", { author: sr.author })}
            </Text>
          )}
          {sr.review_id ? (
            <Anchor component={Link} to={`/reviews/${sr.review_id}`} size="xs">
              {t("selfReview.attachedTo", { id: sr.review_id })}
            </Anchor>
          ) : (
            <Text size="xs" c="dimmed">
              · {t("selfReview.standalone")}
            </Text>
          )}
        </Group>
      )}

      <Group gap="xs" mb={open ? "xs" : 0}>
        <Text size="xs" c="dimmed">
          {t(`selfReview.lane.${sr.lane}`)}
        </Text>
        <Text size="xs" c="dimmed">
          · {t("selfReview.findings", { count: sr.finding_count })}
        </Text>
        {/* What the findings actually are, without paying for them: the counts ride along with
            the summary, so a collapsed card still says "5 major, 3 minor" rather than just "9". */}
        {SEVERITY_ORDER.filter((s) => sr.severity_counts?.[s]).map((s) => (
          <Badge key={s} size="sm" color={SEVERITY_COLOR[s]} variant="light">
            {sr.severity_counts[s]} {t(`selfReview.severity.${s}`)}
          </Badge>
        ))}
        {collapsible && (
          <Button size="compact-xs" variant="subtle" onClick={() => setOpen((v) => !v)} ml="auto">
            {open ? t("selfReview.hide") : t("selfReview.show")}
          </Button>
        )}
      </Group>

      <Collapse in={open}>
        {data?.summary && (
          <Text size="sm" mb="xs" style={{ whiteSpace: "pre-wrap" }}>
            {data.summary}
          </Text>
        )}
        {findings.length > 0 ? (
          <Stack gap="xs">
            {findings.map((f, i) => (
              <Finding key={`${f.file ?? ""}-${f.line ?? 0}-${i}`} f={f} />
            ))}
          </Stack>
        ) : (
          data && (
            <Text size="sm" c="dimmed">
              {t("selfReview.noFindings")}
            </Text>
          )
        )}
      </Collapse>
    </Card>
  );
}
