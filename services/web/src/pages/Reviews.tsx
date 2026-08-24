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
import { api, TaskReviewSummary } from "../api";
import SelfReviewPolicy from "../components/SelfReviewPolicy";
import { useI18n } from "../i18n";
import type { TFunc } from "../i18n";

export const STATUS_COLOR: Record<string, string> = {
  changes_needed: "orange",
  passed: "blue",
  approved: "green",
};

export function StatusBadge({ status, t }: { status: string; t: TFunc }) {
  return (
    <Badge color={STATUS_COLOR[status] ?? "gray"} variant="light">
      {t(`board.status.${status}`)}
    </Badge>
  );
}

function TaskCard({ task, t }: { task: TaskReviewSummary; t: TFunc }) {
  return (
    <Card withBorder radius="md" padding="md" component={Link} to={`/reviews/${task.id}`}>
      <Group justify="space-between" wrap="nowrap" mb="xs">
        <Text fw={600} truncate>
          {task.title || task.task_ref}
        </Text>
        <StatusBadge status={task.status} t={t} />
      </Group>
      <Text size="xs" c="dimmed">
        {t("reviews.task")}: {task.task_ref}
        {task.branch ? ` · ${task.branch}` : ""}
      </Text>
      <Group gap="xs" mt="xs">
        <Text size="xs" c="dimmed">
          {t("reviews.by", { author: task.author ?? "—" })}
        </Text>
        <Text size="xs" c="dimmed">
          · {t("board.runs", { count: task.run_count })}
        </Text>
        {task.open_finding_count > 0 && (
          <Text size="xs" c="orange">
            · {t("board.openFindings", { count: task.open_finding_count })}
          </Text>
        )}
        {task.approved_by && (
          <Text size="xs" c="teal">
            · {t("board.approvedBy", { who: task.approved_by })}
          </Text>
        )}
      </Group>
      {task.lead_comment && (
        <Text size="xs" c="orange" mt={6} lineClamp={2}>
          {t("board.leadSaid")}: {task.lead_comment}
        </Text>
      )}
    </Card>
  );
}

type Tab = "queue" | "open" | "mine" | "all";

// The lead's queue is `passed`: the developer's own review came back clean, so the task is waiting
// for a sign-off. `open` is what is still with its author, either from the run or from a return.
const TAB_PARAMS: Record<string, Parameters<typeof api.listTaskReviews>[0]> = {
  queue: { status: "passed" },
  open: { status: "changes_needed" },
  mine: { mine: true },
  all: {},
};

export default function Reviews() {
  const { t } = useI18n();
  const [tab, setTab] = useState<Tab>("queue");

  const query = useQuery({
    queryKey: ["taskReviews", tab],
    queryFn: () => api.listTaskReviews(TAB_PARAMS[tab]),
  });
  const items = query.data ?? [];

  return (
    <Container size="xl">
      <Stack gap="md">
        <div>
          <Title order={2}>{t("reviews.title")}</Title>
          <Text c="dimmed" size="sm">
            {t("board.count", { count: items.length })}
          </Text>
        </div>

        <Text c="dimmed" size="sm">
          {t("reviews.intro")}
        </Text>

        <SegmentedControl
          value={tab}
          onChange={(v) => setTab(v as Tab)}
          data={[
            { label: t("board.queueTab"), value: "queue" },
            { label: t("board.openTab"), value: "open" },
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
            {t("board.empty")}
          </Text>
        ) : (
          <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
            {items.map((task) => (
              <TaskCard key={task.id} task={task} t={t} />
            ))}
          </SimpleGrid>
        )}

        <SelfReviewPolicy />

        <Alert variant="light" color="gray" mt="md">
          {t("reviews.usageHint")}
        </Alert>
      </Stack>
    </Container>
  );
}
