import {
  Badge,
  Button,
  Card,
  Code,
  Container,
  CopyButton,
  Group,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { api, Recommendation } from "../api";
import PageLoader from "../components/PageLoader";
import { useI18n } from "../i18n";

const KIND_COLOR: Record<string, string> = {
  synthesize: "grape",
  split: "blue",
  improve: "indigo",
  merge: "teal",
  dedup: "cyan",
  delete: "red",
  other: "gray",
};

const STATUS_COLOR: Record<string, string> = {
  proposed: "yellow",
  accepted: "blue",
  done: "green",
  dismissed: "gray",
};

const STATUS_ORDER: Record<string, number> = { proposed: 0, accepted: 1, done: 2, dismissed: 3 };

function RecommendationCard({ r }: { r: Recommendation }) {
  const { t } = useI18n();
  const resolved = r.status === "done" || r.status === "dismissed";
  return (
    <Card withBorder radius="md" padding="md" style={{ opacity: resolved ? 0.65 : 1 }}>
      <Group justify="space-between" align="center" mb={6} wrap="nowrap">
        <Group gap="xs" wrap="nowrap">
          <Badge color={KIND_COLOR[r.kind] ?? "gray"} variant="filled">
            {r.kind}
          </Badge>
          <Text fw={600}>{r.title}</Text>
        </Group>
        <Badge color={STATUS_COLOR[r.status] ?? "gray"} variant="light">
          {r.status}
        </Badge>
      </Group>

      <Text size="sm" c="dimmed" mb="sm">
        {r.rationale}
      </Text>

      <Group gap="xs" mb="sm">
        {r.scope && (
          <Badge size="sm" variant="outline" styles={{ label: { textTransform: "none" } }}>
            {t("rec.scope", { v: r.scope })}
          </Badge>
        )}
        {r.targets.map((t, i) => (
          <Badge
            key={`${r.id}-${i}`}
            size="sm"
            variant="dot"
            styles={{ label: { textTransform: "none" } }}
          >
            {t}
          </Badge>
        ))}
      </Group>

      {r.suggested_action && (
        <>
          <Group justify="space-between" align="center" mb={4}>
            <Text size="xs" c="dimmed">
              {t("rec.runThis")}
            </Text>
            <CopyButton value={r.suggested_action}>
              {({ copied, copy }) => (
                <Button size="compact-xs" variant="light" color={copied ? "teal" : "gray"} onClick={copy}>
                  {copied ? t("common.copied") : t("common.copy")}
                </Button>
              )}
            </CopyButton>
          </Group>
          <Code block style={{ whiteSpace: "pre-wrap" }}>
            {r.suggested_action}
          </Code>
        </>
      )}
    </Card>
  );
}

export default function Recommendations() {
  const { t } = useI18n();
  const { data, isLoading } = useQuery({
    queryKey: ["recommendations"],
    queryFn: api.listRecommendations,
  });

  if (isLoading) {
    return <PageLoader />;
  }

  const recs = [...(data ?? [])].sort(
    (a, b) => (STATUS_ORDER[a.status] ?? 9) - (STATUS_ORDER[b.status] ?? 9),
  );
  const open = recs.filter((r) => r.status === "proposed" || r.status === "accepted");

  return (
    <Container size="md">
      <Stack gap="lg">
        <div>
          <Group gap="sm" align="center">
            <Title order={2}>{t("rec.title")}</Title>
            <Badge variant="light">{t("rec.open", { count: open.length })}</Badge>
          </Group>
          <Text c="dimmed" size="sm">
            {t("rec.intro")}
          </Text>
        </div>

        {recs.length === 0 ? (
          <Text c="dimmed" ta="center" mt="xl">
            {t("rec.empty")}
          </Text>
        ) : (
          <Stack gap="md">
            {recs.map((r) => (
              <RecommendationCard key={r.id} r={r} />
            ))}
          </Stack>
        )}
      </Stack>
    </Container>
  );
}
