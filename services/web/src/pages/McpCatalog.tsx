import {
  Badge,
  Card,
  Container,
  Group,
  Loader,
  Select,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, McpServerSummary } from "../api";
import { ScoreBadge } from "../components/Score";
import { useI18n } from "../i18n";
import { KIND_COLOR } from "./Recommendations";

// ~4 chars/token, the same rough heuristic the server used to produce the estimate.
function formatTokens(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}

function McpCard({ server }: { server: McpServerSummary }) {
  const { t } = useI18n();
  return (
    <Card withBorder padding="md" radius="md" component={Link} to={`/mcp/${server.id}`}>
      <Group justify="space-between" wrap="nowrap" mb="xs">
        <Text fw={600} ff="monospace" truncate>
          {server.name}
        </Text>
        <ScoreBadge value={server.overall_score} size="sm" />
      </Group>
      <Text size="xs" c="dimmed" mb="xs">
        {t("mcp.toolCount", { n: server.tool_count })}
        {` · ${server.transport}`}
        {server.estimated_tokens != null &&
          ` · ${t("mcp.surfaceTokens", { n: formatTokens(server.estimated_tokens) })}`}
      </Text>
      <Text size="sm" lineClamp={3} mb="sm">
        {server.description || t("mcp.noDescription")}
      </Text>
      <Group gap={4}>
        {server.open_improve_count > 0 && (
          <Badge color={KIND_COLOR.improve} variant="filled" size="sm">
            {t("catalog.openImprove", { n: server.open_improve_count })}
          </Badge>
        )}
        {server.family && (
          <Badge variant="light" size="sm">
            {server.family}
          </Badge>
        )}
      </Group>
    </Card>
  );
}

export default function McpCatalog() {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const [family, setFamily] = useState<string | null>(null);
  const [debounced] = useDebouncedValue(search, 300);

  const { data: servers, isLoading } = useQuery({
    queryKey: ["mcp-servers", debounced, family],
    queryFn: () => api.listMcpServers(debounced || undefined, family ?? undefined),
  });

  // Families come from the loaded rows rather than their own endpoint — the catalog is small and
  // this keeps the filter honest about what's actually present.
  const families = Array.from(
    new Set((servers ?? []).map((s) => s.family).filter((f): f is string => !!f)),
  ).sort();

  return (
    <Container size="xl">
      <Stack gap="md">
        <div>
          <Title order={2}>{t("mcp.title")}</Title>
          <Text c="dimmed" size="sm">
            {t("mcp.subtitle")}
          </Text>
        </div>

        <Group>
          <TextInput
            placeholder={t("mcp.searchPlaceholder")}
            value={search}
            onChange={(e) => setSearch(e.currentTarget.value)}
            style={{ flex: 1, minWidth: 220 }}
          />
          <Select
            placeholder={t("mcp.allFamilies")}
            data={families}
            value={family}
            onChange={setFamily}
            clearable
            w={220}
          />
        </Group>

        {isLoading ? (
          <Group justify="center" mt="xl">
            <Loader />
          </Group>
        ) : (servers ?? []).length === 0 ? (
          <Text c="dimmed">{t("mcp.empty")}</Text>
        ) : (
          <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }}>
            {(servers ?? []).map((s) => (
              <McpCard key={s.id} server={s} />
            ))}
          </SimpleGrid>
        )}
      </Stack>
    </Container>
  );
}
