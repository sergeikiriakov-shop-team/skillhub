import { Badge, Container, Group, Stack, Text, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import PageLoader from "../components/PageLoader";
import { useI18n } from "../i18n";
import { RecommendationCard, STATUS_ORDER } from "./Recommendations";

export default function McpRecommendations() {
  const { t } = useI18n();
  const { data, isLoading } = useQuery({
    queryKey: ["recommendations", "mcp"],
    queryFn: () => api.listRecommendations("mcp"),
  });

  if (isLoading) return <PageLoader />;

  const recs = [...(data ?? [])].sort(
    (a, b) => (STATUS_ORDER[a.status] ?? 9) - (STATUS_ORDER[b.status] ?? 9),
  );
  const open = recs.filter((r) => r.status === "proposed" || r.status === "accepted");

  return (
    <Container size="md">
      <Stack gap="lg">
        <div>
          <Group gap="sm" align="center">
            <Title order={2}>{t("mcpRec.title")}</Title>
            <Badge variant="light">{t("rec.open", { count: open.length })}</Badge>
          </Group>
          <Text c="dimmed" size="sm">
            {t("mcpRec.intro")}
          </Text>
        </div>

        {recs.length === 0 ? (
          <Text c="dimmed" ta="center" mt="xl">
            {t("mcpRec.empty")}
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
