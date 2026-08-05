import {
  Alert,
  Badge,
  Button,
  Card,
  Code,
  Container,
  CopyButton,
  Divider,
  Grid,
  Group,
  List,
  Paper,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { api } from "../api";
import type { McpToolDef, Recommendation } from "../api";
import PageLoader from "../components/PageLoader";
import { ScoreBadge, ScoreBreakdown } from "../components/Score";
import { useI18n } from "../i18n";
import { KIND_COLOR } from "./Recommendations";

// The MCP rubric's dimensions, in rubric order (see mcp/rubric.py) — not the skills ones.
const MCP_DIMENSION_KEYS = [
  "schema_precision",
  "tool_clarity",
  "discoverability",
  "result_shape",
  "safety",
  "token_economy",
];

interface SchemaProp {
  name: string;
  type: string;
  required: boolean;
  description: string;
}

// Flatten a tool's JSON-Schema `properties` into the rows the params table renders. Kept tolerant:
// a hand-written or partial schema still yields whatever it does declare, and an absent type shows
// as "—" rather than being guessed — an untyped param is a real finding, not a rendering gap.
function schemaProps(tool: McpToolDef): SchemaProp[] {
  const rawProps = tool.input_schema?.properties;
  const properties: Record<string, Record<string, unknown>> =
    rawProps && typeof rawProps === "object"
      ? (rawProps as Record<string, Record<string, unknown>>)
      : {};
  return Object.entries(properties).map(([name, spec]) => {
    const field: Record<string, unknown> = spec ?? {};
    // `anyOf` is how an optional param is usually expressed (e.g. string | null) — unwrap it so the
    // table shows "string" rather than an opaque blank.
    const anyOf = Array.isArray(field.anyOf) ? (field.anyOf as Record<string, unknown>[]) : null;
    const type = anyOf
      ? anyOf
          .map((v) => String(v.type ?? "?"))
          .filter((v) => v !== "null")
          .join(" | ")
      : field.type != null
        ? String(field.type)
        : "—";
    return {
      name,
      type,
      required: tool.required.includes(name),
      description: typeof field.description === "string" ? field.description : "",
    };
  });
}

// The same dashed-indigo inline treatment the skill page uses under a SKILL.md heading — here it
// sits under the specific tool the recommendation's `anchor` names.
function InlineSuggestion({ rec }: { rec: Recommendation }) {
  const { t } = useI18n();
  return (
    <Paper
      withBorder
      radius="sm"
      p="sm"
      mt={6}
      style={{
        borderColor: "var(--mantine-color-indigo-4)",
        borderStyle: "dashed",
        background: "var(--mantine-color-indigo-light)",
      }}
    >
      <Group gap="xs" mb={4} wrap="nowrap">
        <Badge color={KIND_COLOR.improve} variant="filled" size="sm">
          {t("detail.insertHere")}
        </Badge>
        <Text size="sm" fw={600}>
          {rec.title}
        </Text>
      </Group>
      {rec.suggested_action && (
        <Text
          size="xs"
          ff="monospace"
          style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}
        >
          {rec.suggested_action}
        </Text>
      )}
    </Paper>
  );
}

function ToolCard({ tool, suggestions }: { tool: McpToolDef; suggestions: Recommendation[] }) {
  const { t } = useI18n();
  const props = schemaProps(tool);
  return (
    <div>
      <Paper withBorder radius="sm" p="sm">
        <Group justify="space-between" wrap="nowrap" mb={4}>
          <Text ff="monospace" fw={600} size="sm">
            {tool.name}
          </Text>
          <Badge variant="light" size="sm">
            {t("mcp.paramCount", { n: tool.param_count })}
          </Badge>
        </Group>
        {tool.description ? (
          <Text size="xs" c="dimmed" style={{ whiteSpace: "pre-wrap" }}>
            {tool.description}
          </Text>
        ) : (
          <Text size="xs" c="orange">
            {t("mcp.noToolDescription")}
          </Text>
        )}
        {props.length > 0 && (
          <Table mt="xs" fz="xs" verticalSpacing={4}>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t("mcp.param")}</Table.Th>
                <Table.Th>{t("mcp.type")}</Table.Th>
                <Table.Th>{t("mcp.paramDescription")}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {props.map((p) => (
                <Table.Tr key={p.name}>
                  <Table.Td>
                    <Text ff="monospace" fz="xs" span>
                      {p.name}
                    </Text>
                    {p.required && (
                      <Text span c="red" fz="xs" fw={700}>
                        {" *"}
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Text ff="monospace" fz="xs" c="dimmed" span>
                      {p.type}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text fz="xs" c="dimmed" span>
                      {p.description || "—"}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Paper>
      {suggestions.map((r) => (
        <InlineSuggestion key={r.id} rec={r} />
      ))}
    </div>
  );
}

export default function McpDetail() {
  const { t } = useI18n();
  const { id } = useParams();
  const serverId = Number(id);

  const { data: server, isLoading } = useQuery({
    queryKey: ["mcp-server", serverId],
    queryFn: () => api.getMcpServer(serverId),
  });

  if (isLoading) return <PageLoader />;
  if (!server) {
    return (
      <Container>
        <Alert color="red">{t("mcp.notFound")}</Alert>
      </Container>
    );
  }

  const evalr = server.latest_evaluation;
  const recs = server.open_recommendations;
  // An `improve` rec whose anchor names a tool renders inline under that tool (below); the rest
  // only appear in the side list, so nothing is silently dropped either way.
  const byTool = (toolName: string) =>
    recs.filter(
      (r) =>
        r.kind === "improve" &&
        r.anchor &&
        r.anchor.trim().toLowerCase() === toolName.toLowerCase(),
    );

  return (
    <Container size="xl">
      <Stack gap="md">
        <div>
          <Group gap="sm">
            <Title order={2} ff="monospace">
              {server.name}
            </Title>
            <ScoreBadge value={server.overall_score} />
            {server.open_improve_count > 0 && (
              <Badge color={KIND_COLOR.improve} variant="filled">
                {t("catalog.openImprove", { n: server.open_improve_count })}
              </Badge>
            )}
          </Group>
          <Text c="dimmed" size="sm">
            {t("mcp.meta", {
              transport: server.transport,
              version: server.version_no,
              tools: server.tool_count,
            })}
          </Text>
          {server.family && (
            <Group gap={4} mt="xs">
              <Badge variant="light">{server.family}</Badge>
            </Group>
          )}
        </div>

        <Grid>
          <Grid.Col span={{ base: 12, md: 8 }}>
            {server.description && (
              <Alert color="indigo" variant="light" mb="md">
                {server.description}
              </Alert>
            )}

            <Card withBorder radius="md" padding="md">
              <Text fw={600} mb={2}>
                🧩 {t("mcp.toolsTitle")}
              </Text>
              <Text size="xs" c="dimmed" mb="sm">
                {t("mcp.toolsHint")}
              </Text>
              {server.tools.length === 0 ? (
                <Text size="sm" c="dimmed">
                  {t("mcp.noTools")}
                </Text>
              ) : (
                <Stack gap="sm">
                  {server.tools.map((tool) => (
                    <ToolCard key={tool.name} tool={tool} suggestions={byTool(tool.name)} />
                  ))}
                </Stack>
              )}
            </Card>
          </Grid.Col>

          <Grid.Col span={{ base: 12, md: 4 }}>
            {recs.length > 0 && (
              <Card
                withBorder
                radius="md"
                padding="md"
                mb="md"
                style={{ borderColor: "var(--mantine-color-indigo-4)" }}
              >
                <Text fw={600} mb="sm">
                  ✨ {t("detail.improvements", { count: recs.length })}
                </Text>
                <Stack gap="sm">
                  {recs.map((r) => (
                    <Paper key={r.id} withBorder radius="sm" p="sm">
                      <Group gap="xs" mb={4} wrap="nowrap">
                        <Badge color={KIND_COLOR[r.kind] ?? "gray"} variant="filled" size="sm">
                          {r.kind}
                        </Badge>
                        {r.anchor && (
                          <Badge variant="outline" size="sm" ff="monospace">
                            {r.anchor}
                          </Badge>
                        )}
                      </Group>
                      <Text size="sm" fw={600} mb={4}>
                        {r.title}
                      </Text>
                      <Text size="xs" c="dimmed" mb={r.suggested_action ? 6 : 0}>
                        {r.rationale}
                      </Text>
                      {r.suggested_action && (
                        <>
                          <Group justify="space-between" align="center" mb={4}>
                            <Text size="xs" c="dimmed">
                              {t("rec.runThis")}
                            </Text>
                            <CopyButton value={r.suggested_action}>
                              {({ copied, copy }) => (
                                <Button
                                  size="compact-xs"
                                  variant="light"
                                  color={copied ? "teal" : "gray"}
                                  onClick={copy}
                                >
                                  {copied ? t("common.copied") : t("common.copy")}
                                </Button>
                              )}
                            </CopyButton>
                          </Group>
                          <Paper
                            p="xs"
                            bg="var(--mantine-color-default-hover)"
                            style={{
                              whiteSpace: "pre-wrap",
                              overflowWrap: "anywhere",
                              fontFamily: "monospace",
                              fontSize: 12,
                            }}
                          >
                            {r.suggested_action}
                          </Paper>
                        </>
                      )}
                    </Paper>
                  ))}
                </Stack>
              </Card>
            )}

            <Card withBorder radius="md" padding="md">
              <Text fw={600} mb="sm">
                {t("mcp.evalTitle")}
              </Text>
              {evalr ? (
                <Stack gap="sm">
                  <ScoreBreakdown scores={evalr.scores} dimensionKeys={MCP_DIMENSION_KEYS} />
                  <Divider />
                  {evalr.strengths.length > 0 && (
                    <div>
                      <Text size="sm" fw={600} c="teal">
                        {t("detail.strengths")}
                      </Text>
                      <List size="sm">
                        {evalr.strengths.map((s, i) => (
                          <List.Item key={i}>{s}</List.Item>
                        ))}
                      </List>
                    </div>
                  )}
                  {evalr.weaknesses.length > 0 && (
                    <div>
                      <Text size="sm" fw={600} c="orange">
                        {t("detail.weaknesses")}
                      </Text>
                      <List size="sm">
                        {evalr.weaknesses.map((w, i) => (
                          <List.Item key={i}>{w}</List.Item>
                        ))}
                      </List>
                    </div>
                  )}
                  {evalr.rationale && (
                    <Text size="sm" c="dimmed" fs="italic">
                      {evalr.rationale}
                    </Text>
                  )}
                  <Text size="xs" c="dimmed">
                    {t("detail.evalMeta", {
                      model: evalr.model,
                      version: evalr.rubric_version,
                    })}
                  </Text>
                </Stack>
              ) : (
                <Stack gap="xs">
                  <Text size="sm" c="dimmed">
                    {t("mcp.notEvaluated")}
                  </Text>
                  <Code block style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>
                    {t("mcp.evaluatePhrase", { name: server.name })}
                  </Code>
                </Stack>
              )}
            </Card>

            <Card withBorder radius="md" padding="md" mt="md">
              <Text fw={600} mb={2}>
                {t("mcp.historyTitle")}
              </Text>
              <Text size="xs" c="dimmed" mb="sm">
                {t("mcp.historyHint")}
              </Text>
              {server.contributors.length > 0 && (
                <Group gap={4} mb="sm">
                  {server.contributors.map((c) => (
                    <Badge key={c} variant="light" size="sm">
                      {c}
                    </Badge>
                  ))}
                </Group>
              )}
              <Stack gap={4}>
                {server.versions.map((v) => (
                  <Group key={v.version_no} justify="space-between" wrap="nowrap">
                    <Text size="sm">
                      v{v.version_no} · {t("mcp.toolCount", { n: v.tool_count })}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {new Date(v.created_at).toLocaleDateString()}
                    </Text>
                  </Group>
                ))}
              </Stack>
            </Card>
          </Grid.Col>
        </Grid>
      </Stack>
    </Container>
  );
}
