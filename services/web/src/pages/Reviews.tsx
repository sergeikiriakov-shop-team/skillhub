import {
  Alert,
  Badge,
  Card,
  Container,
  Group,
  Loader,
  SegmentedControl,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ReviewSummary } from "../api";
import { useI18n } from "../i18n";
import type { TFunc } from "../i18n";

export const STATUS_COLOR: Record<string, string> = {
  submitted: "blue",
  changes_requested: "orange",
  approved: "green",
  done: "gray",
};

export function StatusBadge({ status, t }: { status: string; t: TFunc }) {
  return (
    <Badge color={STATUS_COLOR[status] ?? "gray"} variant="light">
      {t(`reviews.status.${status}`)}
    </Badge>
  );
}

function ReviewCard({ r, t }: { r: ReviewSummary; t: TFunc }) {
  return (
    <Card withBorder radius="md" padding="md" component={Link} to={`/reviews/${r.id}`}>
      <Group justify="space-between" wrap="nowrap" mb="xs">
        <Text fw={600} truncate>
          {r.title || r.task_ref}
        </Text>
        <StatusBadge status={r.status} t={t} />
      </Group>
      <Text size="xs" c="dimmed">
        {t("reviews.task")}: {r.task_ref}
        {r.branch ? ` · ${r.branch}` : ""}
      </Text>
      <Group gap="xs" mt="xs">
        <Text size="xs" c="dimmed">
          {t("reviews.by", { author: r.author ?? "—" })}
        </Text>
        <Text size="xs" c="dimmed">
          · {t("reviews.reviewer", { who: r.reviewer ?? t("reviews.unassigned") })}
        </Text>
      </Group>
    </Card>
  );
}

type Tab = "queue" | "mine" | "all";

export default function Reviews() {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("queue");

  const query = useQuery({
    queryKey: ["reviews", tab],
    queryFn: () =>
      api.listReviews(
        tab === "queue" ? { status: "submitted" } : tab === "mine" ? { mine: true } : {},
      ),
  });
  const items = query.data ?? [];

  return (
    <Container size="xl">
      <Stack gap="md">
        <div>
          <Title order={2}>{t("reviews.title")}</Title>
          <Text c="dimmed" size="sm">
            {t("reviews.count", { count: items.length })}
          </Text>
        </div>

        <Text c="dimmed" size="sm">
          {t("reviews.intro")}
        </Text>

        <SegmentedControl
          value={tab}
          onChange={(v) => setTab(v as Tab)}
          data={[
            { label: t("reviews.queueTab"), value: "queue" },
            { label: t("reviews.mineTab"), value: "mine" },
            { label: t("reviews.allTab"), value: "all" },
          ]}
        />

        {query.isLoading ? (
          <Group justify="center" mt="xl">
            <Loader />
          </Group>
        ) : items.length === 0 ? (
          <Text c="dimmed" ta="center" mt="xl">
            {t("reviews.empty")}
          </Text>
        ) : (
          <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
            {items.map((r) => (
              <ReviewCard key={r.id} r={r} t={t} />
            ))}
          </SimpleGrid>
        )}

        <Alert variant="light" color="gray" mt="md">
          {t("reviews.usageHint")}
        </Alert>
      </Stack>
    </Container>
  );
}
