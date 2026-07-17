import {
  Badge,
  Card,
  Code,
  Container,
  Group,
  Loader,
  Paper,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useParams } from "react-router-dom";
import { api, ReviewEvent } from "../api";
import { useI18n } from "../i18n";
import { STATUS_COLOR, StatusBadge } from "./Reviews";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <Text size="xs" c="dimmed" tt="uppercase" fw={600} mb={2}>
        {label}
      </Text>
      {children}
    </div>
  );
}

function ThreadItem({ ev }: { ev: ReviewEvent }) {
  const { t } = useI18n();
  const isVerdict = ev.kind === "verdict";
  const color = isVerdict ? STATUS_COLOR[ev.verdict === "approve" ? "approved" : "changes_requested"] : "gray";
  return (
    <Paper withBorder radius="md" p="sm">
      <Group justify="space-between" mb={ev.body ? "xs" : 0} wrap="nowrap">
        <Group gap="xs" wrap="nowrap">
          <Badge size="sm" color={color} variant="light">
            {t(`reviews.event.${ev.kind}`)}
          </Badge>
          {ev.author && (
            <Text size="xs" c="dimmed">
              {ev.author}
            </Text>
          )}
        </Group>
        <Text size="xs" c="dimmed">
          {new Date(ev.created_at).toLocaleString()}
        </Text>
      </Group>
      {ev.body && (
        <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
          {ev.body}
        </Text>
      )}
    </Paper>
  );
}

export default function ReviewDetail() {
  const { t } = useI18n();
  const { id } = useParams();
  const { data: r, isLoading } = useQuery({
    queryKey: ["review", id],
    queryFn: () => api.getReview(Number(id)),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <Group justify="center" mt="xl">
        <Loader />
      </Group>
    );
  }
  if (!r) {
    return (
      <Container size="md">
        <Text c="dimmed" mt="xl">
          {t("reviews.notFound")}
        </Text>
      </Container>
    );
  }

  return (
    <Container size="md">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <div>
            <Title order={2}>{r.title || r.task_ref}</Title>
            <Text c="dimmed" size="sm">
              {t("reviews.by", { author: r.author ?? "—" })} ·{" "}
              {t("reviews.reviewer", { who: r.reviewer ?? t("reviews.unassigned") })}
            </Text>
          </div>
          <StatusBadge status={r.status} t={t} />
        </Group>

        <Card withBorder radius="md" padding="md">
          <Stack gap="sm">
            <Group gap="xl" wrap="wrap">
              <Field label={t("reviews.task")}>
                <Text size="sm">{r.task_ref}</Text>
              </Field>
              <Field label={t("reviews.branch")}>
                <Text size="sm">{r.branch || "—"}</Text>
              </Field>
            </Group>
            {r.commit_shas.length > 0 && (
              <Field label={t("reviews.commits")}>
                <Group gap={4}>
                  {r.commit_shas.map((c) => (
                    <Code key={c}>{c.slice(0, 10)}</Code>
                  ))}
                </Group>
              </Field>
            )}
            {r.files.length > 0 && (
              <Field label={t("reviews.files")}>
                <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                  {r.files.join("\n")}
                </Text>
              </Field>
            )}
            {r.summary && (
              <Field label={t("reviews.summary")}>
                <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                  {r.summary}
                </Text>
              </Field>
            )}
            {r.verified_notes && (
              <Field label={t("reviews.verified")}>
                <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                  {r.verified_notes}
                </Text>
              </Field>
            )}
          </Stack>
        </Card>

        <div>
          <Title order={4} mb="xs">
            {t("reviews.thread")}
          </Title>
          <Stack gap="xs">
            {r.events.map((ev) => (
              <ThreadItem key={ev.id} ev={ev} />
            ))}
          </Stack>
        </div>
      </Stack>
    </Container>
  );
}
