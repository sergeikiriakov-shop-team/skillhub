import { Badge, Card, Code, Group, Paper, Stack, Text } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import type { SelfReviewFinding, SelfReviewSummary } from "../api";
import { useI18n } from "../i18n";

const SEVERITY_COLOR: Record<string, string> = {
  blocker: "red",
  major: "orange",
  minor: "yellow",
  nit: "gray",
};

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

/** One self-review attached to a peer review: what the team's review skill found in the author's
 * own change, before the lead ever saw it. The summary comes with the review; the findings are
 * fetched on demand (they are the heavy half). */
export default function SelfReviewCard({ sr }: { sr: SelfReviewSummary }) {
  const { t } = useI18n();
  const { data } = useQuery({
    queryKey: ["selfReview", sr.id],
    queryFn: () => api.getSelfReview(sr.id),
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

      <Group gap="xs" mb={data?.summary ? "xs" : 0}>
        <Text size="xs" c="dimmed">
          {t(`selfReview.lane.${sr.lane}`)}
        </Text>
        <Text size="xs" c="dimmed">
          · {t("selfReview.findings", { count: sr.finding_count })}
        </Text>
        {sr.blocking_count > 0 && (
          <Text size="xs" c="orange">
            · {t("selfReview.blocking", { count: sr.blocking_count })}
          </Text>
        )}
      </Group>

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
        <Text size="sm" c="dimmed">
          {t("selfReview.noFindings")}
        </Text>
      )}
    </Card>
  );
}
