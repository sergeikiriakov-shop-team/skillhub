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
import { useAuth } from "../auth";
import SelfReviewCard from "../components/SelfReviewCard";
import SelfReviewPolicy from "../components/SelfReviewPolicy";
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

type Tab = "queue" | "assigned" | "mine" | "all" | "self";

// The board is open-review by default (anyone may pick a task up), so "queue" is every submitted
// review — not just the ones assigned to you. A designated lead (`is_reviewer`) additionally gets
// "assigned to me", which is what `queue=true` filters on server-side.
const TAB_PARAMS: Record<string, Parameters<typeof api.listReviews>[0]> = {
  queue: { status: "submitted" },
  assigned: { queue: true, status: "submitted" },
  mine: { mine: true },
  all: {},
};

export default function Reviews() {
  const { t } = useI18n();
  const { me } = useAuth();
  const [tab, setTab] = useState<Tab>("queue");
  const isReviewer = !!me?.is_reviewer;

  const query = useQuery({
    queryKey: ["reviews", tab],
    queryFn: () => api.listReviews(TAB_PARAMS[tab]),
    enabled: tab !== "self",
  });
  // Self-reviews live independently of the board: one exists as soon as a developer runs the
  // configured skill on their own diff, whether or not the task was ever handed to a lead.
  const selfQuery = useQuery({
    queryKey: ["selfReviews"],
    queryFn: () => api.listSelfReviews(),
    enabled: tab === "self",
  });
  const items = query.data ?? [];
  const selfItems = selfQuery.data ?? [];
  const isSelf = tab === "self";
  const loading = isSelf ? selfQuery.isLoading : query.isLoading;
  const count = isSelf ? selfItems.length : items.length;

  return (
    <Container size="xl">
      <Stack gap="md">
        <div>
          <Title order={2}>{t("reviews.title")}</Title>
          <Text c="dimmed" size="sm">
            {isSelf ? t("selfReview.count", { count }) : t("reviews.count", { count })}
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
            ...(isReviewer ? [{ label: t("reviews.assignedTab"), value: "assigned" }] : []),
            { label: t("reviews.mineTab"), value: "mine" },
            { label: t("reviews.allTab"), value: "all" },
            { label: t("reviews.selfTab"), value: "self" },
          ]}
        />

        {loading ? (
          <Group justify="center" mt="xl">
            <Loader />
          </Group>
        ) : count === 0 ? (
          <Text c="dimmed" ta="center" mt="xl">
            {isSelf ? t("selfReview.empty") : t("reviews.empty")}
          </Text>
        ) : isSelf ? (
          <Stack gap="sm">
            {selfItems.map((sr) => (
              <SelfReviewCard key={sr.id} sr={sr} collapsible showTask />
            ))}
          </Stack>
        ) : (
          <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
            {items.map((r) => (
              <ReviewCard key={r.id} r={r} t={t} />
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
