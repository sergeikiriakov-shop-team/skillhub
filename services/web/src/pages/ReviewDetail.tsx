import {
  Alert,
  Button,
  Card,
  Code,
  Container,
  Group,
  Loader,
  Stack,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import SelfReviewCard from "../components/SelfReviewCard";
import { useI18n } from "../i18n";
import { StatusBadge } from "./Reviews";

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

export default function ReviewDetail() {
  const { t } = useI18n();
  const { me } = useAuth();
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [comment, setComment] = useState("");

  const { data: task, isLoading } = useQuery({
    queryKey: ["taskReview", id],
    queryFn: () => api.getTaskReview(Number(id)),
    enabled: !!id,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["taskReviews"] });
    qc.invalidateQueries({ queryKey: ["taskReview", id] });
  };

  const approve = useMutation({
    mutationFn: () => api.approveTaskReview(Number(id)),
    onSuccess: refresh,
  });
  const sendBack = useMutation({
    mutationFn: () => api.returnTaskReview(Number(id), comment),
    onSuccess: () => {
      setComment("");
      refresh();
    },
  });
  const remove = useMutation({
    mutationFn: () => api.deleteTaskReview(Number(id)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["taskReviews"] });
      navigate("/reviews");
    },
  });

  if (isLoading) {
    return (
      <Group justify="center" mt="xl">
        <Loader />
      </Group>
    );
  }
  if (!task) {
    return (
      <Container size="md">
        <Text c="dimmed" mt="xl">
          {t("board.notFound")}
        </Text>
      </Container>
    );
  }

  // The lead acts on the board; the author may withdraw their own task while it is unapproved.
  const isLead = !!me?.is_reviewer || !!me?.is_admin;
  const canDelete = !!me?.is_admin || (!!me?.name && me.name === task.author);
  const busy = approve.isPending || sendBack.isPending;
  const error = approve.error || sendBack.error || remove.error;

  return (
    <Container size="md">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <div>
            <Title order={2}>{task.title || task.task_ref}</Title>
            <Text c="dimmed" size="sm">
              {t("reviews.by", { author: task.author ?? "—" })} ·{" "}
              {t("board.runs", { count: task.run_count })}
            </Text>
          </div>
          <Group gap="xs" wrap="nowrap">
            <StatusBadge status={task.status} t={t} />
            {canDelete && (
              <Button
                size="compact-xs"
                variant="subtle"
                color="red"
                loading={remove.isPending}
                onClick={() => {
                  if (window.confirm(t("board.confirmDelete"))) remove.mutate();
                }}
              >
                {t("common.delete")}
              </Button>
            )}
          </Group>
        </Group>

        {error && (
          <Text c="red" size="sm">
            {String(error)}
          </Text>
        )}

        <Card withBorder radius="md" padding="md">
          <Stack gap="sm">
            <Group gap="xl" wrap="wrap">
              <Field label={t("reviews.task")}>
                <Text size="sm">{task.task_ref}</Text>
              </Field>
              <Field label={t("reviews.branch")}>
                <Text size="sm">{task.branch || "—"}</Text>
              </Field>
              {task.approved_by && (
                <Field label={t("board.approved")}>
                  <Text size="sm">
                    {task.approved_by}
                    {task.approved_at ? ` · ${new Date(task.approved_at).toLocaleString()}` : ""}
                  </Text>
                </Field>
              )}
            </Group>
            {task.repo && (
              <Field label={t("board.repo")}>
                <Code>{task.repo}</Code>
              </Field>
            )}
          </Stack>
        </Card>

        {task.lead_comment && (
          <Alert variant="light" color="orange" title={t("board.leadSaid")}>
            <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
              {task.lead_comment}
            </Text>
          </Alert>
        )}

        {isLead && task.status !== "approved" && (
          <Card withBorder radius="md" padding="md">
            <Title order={5} mb="xs">
              {t("board.leadActions")}
            </Title>
            <Text size="xs" c="dimmed" mb="sm">
              {t("board.leadHint")}
            </Text>
            <Textarea
              value={comment}
              onChange={(e) => setComment(e.currentTarget.value)}
              placeholder={t("board.returnPlaceholder")}
              autosize
              minRows={2}
              mb="sm"
            />
            <Group gap="sm">
              <Button color="green" loading={approve.isPending} disabled={busy} onClick={() => approve.mutate()}>
                {t("board.approve")}
              </Button>
              <Button
                variant="default"
                loading={sendBack.isPending}
                disabled={busy || !comment.trim()}
                onClick={() => sendBack.mutate()}
              >
                {t("board.return")}
              </Button>
            </Group>
          </Card>
        )}

        <div>
          <Title order={4} mb="xs">
            {t("board.latestRun")}
          </Title>
          {task.latest_run ? (
            <SelfReviewCard sr={task.latest_run} />
          ) : (
            <Text c="dimmed" size="sm">
              {t("selfReview.none")}
            </Text>
          )}
        </div>

        {task.self_reviews.length > 1 && (
          <div>
            <Title order={4} mb="xs">
              {t("board.history")}
            </Title>
            <Stack gap="xs">
              {task.self_reviews
                .slice(0, -1)
                .reverse()
                .map((run) => (
                  <SelfReviewCard key={run.id} sr={run} collapsible />
                ))}
            </Stack>
          </div>
        )}
      </Stack>
    </Container>
  );
}
