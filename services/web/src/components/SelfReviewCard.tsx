import { Anchor, Badge, Button, Card, Code, Collapse, Group, Paper, Stack, Text } from "@mantine/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { SelfReviewFinding, SelfReviewSummary } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";

const SEVERITY_COLOR: Record<string, string> = {
  blocker: "red",
  major: "orange",
  minor: "yellow",
  nit: "gray",
};

const SEVERITY_ORDER = ["blocker", "major", "minor", "nit"];

const VERDICT_COLOR: Record<string, string> = { pass: "green", changes_needed: "orange" };

/** A monospace token that opens the repository browser when we know where to point.
 *
 * Kept visibly a link — blue, underlined on hover, with the ↗ that says it leaves the page — because
 * a `file:line` that silently happens to be clickable is a link nobody clicks. */
function CodeLink({ href, label }: { href: string | null; label: string }) {
  if (!href) return <Code>{label}</Code>;
  return (
    <Anchor href={href} target="_blank" rel="noreferrer" title={href}>
      <Code c="blue" style={{ cursor: "pointer" }}>
        {label} ↗
      </Code>
    </Anchor>
  );
}

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
          // Straight to the line, at the commit the review read — not at whatever the branch says
          // today. Rendered as a link only when there is one, so nothing looks clickable in vain.
          <CodeLink href={f.url} label={`${f.file}${f.line ? `:${f.line}` : ""}`} />
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
      {/* What the developer did about it, layered on top — the finding above is still exactly what
          the skill said, so the pair reads as before/after. */}
      {f.fixes?.map((fix) => (
        <Group key={fix.id} gap="xs" mt={6} wrap="nowrap" align="flex-start">
          {/* A commit is evidence; a bare note is the developer's answer — often "not addressed,
              because…". Labelling both "fixed" would misreport the second kind. */}
          <Badge size="sm" color={fix.commit_sha ? "teal" : "gray"} variant="light">
            {fix.commit_sha ? t("selfReview.fixed") : t("selfReview.answered")}
          </Badge>
          {fix.commit_sha && (
            <CodeLink href={fix.commit_url} label={fix.commit_sha.slice(0, 10)} />
          )}
          {fix.note && (
            <Text size="sm" style={{ whiteSpace: "pre-wrap", flex: 1 }}>
              {fix.note}
            </Text>
          )}
        </Group>
      ))}
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
  const { me } = useAuth();
  const qc = useQueryClient();
  const [open, setOpen] = useState(!collapsible);
  // Only the author (or an admin) may delete — mirrors the server rule, so the button never
  // appears where the request would come back 403.
  const canDelete = !!me?.is_admin || (!!me?.name && me.name === sr.author);

  const remove = useMutation({
    mutationFn: () => api.deleteSelfReview(sr.id),
    onSuccess: () => {
      // The peer review's thread loses an entry too, so refresh both lists.
      qc.invalidateQueries({ queryKey: ["selfReviews"] });
      qc.invalidateQueries({ queryKey: ["review"] });
    },
  });
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
        {sr.fixed_count > 0 && (
          <Badge size="sm" color="teal" variant="light">
            {t("selfReview.fixedCount", { fixed: sr.fixed_count, total: sr.finding_count })}
          </Badge>
        )}
        {collapsible && (
          <Button size="compact-xs" variant="subtle" onClick={() => setOpen((v) => !v)} ml="auto">
            {open ? t("selfReview.hide") : t("selfReview.show")}
          </Button>
        )}
        {canDelete && (
          <Button
            size="compact-xs"
            variant="subtle"
            color="red"
            ml={collapsible ? undefined : "auto"}
            loading={remove.isPending}
            onClick={() => {
              // Deleting takes the fixes and the thread entry with it, so make the reader confirm.
              if (window.confirm(t("selfReview.confirmDelete"))) remove.mutate();
            }}
          >
            {t("common.delete")}
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
