import {
  Accordion,
  Alert,
  Anchor,
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
  Loader,
  Paper,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import type { NotebookCell, SkillNotebook, TrialEntry } from "../api";
import { ScoreBadge, ScoreBreakdown } from "../components/Score";
import { useI18n } from "../i18n";
import { KIND_COLOR } from "./Recommendations";

export default function SkillDetail() {
  const { t } = useI18n();
  const { id } = useParams();
  const skillId = Number(id);

  const { data: skill, isLoading } = useQuery({
    queryKey: ["skill", skillId],
    queryFn: () => api.getSkill(skillId),
  });
  const { data: allRecs } = useQuery({
    queryKey: ["recommendations"],
    queryFn: api.listRecommendations,
  });
  const { data: notebook } = useQuery({
    queryKey: ["skill-notebook", skillId],
    queryFn: () => api.getSkillNotebook(skillId),
  });

  if (isLoading) {
    return (
      <Group justify="center" mt="xl">
        <Loader />
      </Group>
    );
  }
  if (!skill) {
    return (
      <Container>
        <Alert color="red">{t("detail.notFound")}</Alert>
      </Container>
    );
  }

  const evalr = skill.latest_evaluation;
  const installPhrase = t("detail.installPhrase", { name: skill.name });

  // Open recommendations that apply to THIS skill: it is a named target, or the scope matches the
  // skill's name / task_group / one of its categories.
  const catKeys = new Set(skill.categories.map((c) => c.key));
  const improvements = (allRecs ?? []).filter(
    (r) =>
      (r.status === "proposed" || r.status === "accepted") &&
      (r.targets.includes(skill.name) ||
        r.scope === skill.name ||
        (skill.task_group != null && r.scope === skill.task_group) ||
        (r.scope != null && catKeys.has(r.scope))),
  );

  return (
    <Container size="xl">
      <Stack gap="md">
        <Group justify="space-between" align="flex-start">
          <div>
            <Group gap="sm">
              <Title order={2}>{skill.name}</Title>
              <ScoreBadge value={skill.overall_score} />
            </Group>
            <Text c="dimmed" size="sm">
              {t("detail.meta", {
                author: skill.author ?? t("catalog.unknownAuthor"),
                version: skill.version_no,
                format: skill.source_format,
              })}
            </Text>
            <Group gap={4} mt="xs">
              {skill.categories.map((c) => (
                <Badge key={c.key} variant="light">
                  {c.label}
                  {c.confidence != null && ` ${(c.confidence * 100).toFixed(0)}%`}
                </Badge>
              ))}
            </Group>
          </div>
        </Group>

        <Grid>
          {/* Left: content */}
          <Grid.Col span={{ base: 12, md: 8 }}>
            {skill.trigger_text && (
              <Alert color="indigo" variant="light" title={t("detail.whenToUse")} mb="md">
                {skill.trigger_text}
              </Alert>
            )}
            <Card withBorder radius="md" padding="md">
              <Text fw={600} mb="xs">
                SKILL.md
              </Text>
              <Paper
                p="sm"
                bg="var(--mantine-color-default-hover)"
                style={{ whiteSpace: "pre-wrap", fontFamily: "monospace", fontSize: 13 }}
              >
                {skill.body_md}
              </Paper>
            </Card>

            {skill.references.length > 0 && (
              <Card withBorder radius="md" padding="md" mt="md">
                <Text fw={600} mb="xs">
                  {t("detail.references")}
                </Text>
                <Accordion variant="contained">
                  {skill.references.map((ref) => (
                    <Accordion.Item key={ref.path} value={ref.path}>
                      <Accordion.Control>{ref.path}</Accordion.Control>
                      <Accordion.Panel>
                        <Paper
                          p="sm"
                          style={{
                            whiteSpace: "pre-wrap",
                            fontFamily: "monospace",
                            fontSize: 12,
                          }}
                        >
                          {ref.content}
                        </Paper>
                      </Accordion.Panel>
                    </Accordion.Item>
                  ))}
                </Accordion>
              </Card>
            )}

            <SandboxTrial notebook={notebook} />
          </Grid.Col>

          {/* Right: install + evaluation + similar */}
          <Grid.Col span={{ base: 12, md: 4 }}>
            <Card withBorder radius="md" padding="md" mb="md">
              <Group justify="space-between" align="center" mb="xs" wrap="nowrap">
                <Text fw={600}>{t("detail.installTitle")}</Text>
                <CopyButton value={installPhrase}>
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
              <Text size="sm" c="dimmed" mb={6}>
                {t("detail.installHint")}
              </Text>
              <Code block style={{ whiteSpace: "pre-wrap" }}>
                {installPhrase}
              </Code>
              <Text size="xs" c="dimmed" mt={6}>
                {t("detail.installNote", { name: skill.name })}
              </Text>
            </Card>

            {improvements.length > 0 && (
              <Card
                withBorder
                radius="md"
                padding="md"
                mb="md"
                style={{ borderColor: "var(--mantine-color-indigo-4)" }}
              >
                <Text fw={600} mb="sm">
                  ✨ {t("detail.improvements", { count: improvements.length })}
                </Text>
                <Stack gap="sm">
                  {improvements.map((r) => (
                    <Paper key={r.id} withBorder radius="sm" p="sm">
                      <Group gap="xs" mb={4} wrap="nowrap">
                        <Badge color={KIND_COLOR[r.kind] ?? "gray"} variant="filled" size="sm">
                          {r.kind}
                        </Badge>
                        <Text size="sm" fw={600}>
                          {r.title}
                        </Text>
                      </Group>
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
                          <Code block style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>
                            {r.suggested_action}
                          </Code>
                        </>
                      )}
                    </Paper>
                  ))}
                </Stack>
              </Card>
            )}

            <Card withBorder radius="md" padding="md">
              <Text fw={600} mb="sm">
                {t("detail.qualityEval")}
              </Text>
              {evalr ? (
                <Stack gap="sm">
                  <ScoreBreakdown scores={evalr.scores} />
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
                <Text size="sm" c="dimmed">
                  {t("detail.notEvaluated")}
                </Text>
              )}
            </Card>

            <Card withBorder radius="md" padding="md" mt="md">
              <Text fw={600} mb="sm">
                {t("detail.similar")}
              </Text>
              {skill.similar.length === 0 ? (
                <Text size="sm" c="dimmed">
                  {t("detail.noNeighbours")}
                </Text>
              ) : (
                <Stack gap="xs">
                  {skill.similar.map((s) => (
                    <Group key={s.id} justify="space-between">
                      <Anchor component={Link} to={`/skills/${s.id}`} size="sm">
                        {s.name}
                      </Anchor>
                      <Badge variant="light" size="sm">
                        {(s.similarity * 100).toFixed(0)}%
                      </Badge>
                    </Group>
                  ))}
                </Stack>
              )}
            </Card>

            <Card withBorder radius="md" padding="md" mt="md">
              <Text fw={600} mb="sm">
                {t("detail.versionHistory")}
              </Text>
              {skill.uploaded_by && (
                <Text size="sm" c="dimmed" mb="xs">
                  {t("detail.updatedBy", { who: skill.uploaded_by })}
                </Text>
              )}
              {skill.contributors.length > 0 && (
                <>
                  <Text size="xs" c="dimmed" mb={4}>
                    {t("detail.contributors")}
                  </Text>
                  <Group gap={4} mb="sm">
                    {skill.contributors.map((c) => (
                      <Badge key={c} variant="light" size="sm">
                        {c}
                      </Badge>
                    ))}
                  </Group>
                </>
              )}
              <Stack gap={4}>
                {skill.versions.map((v) => (
                  <Group key={v.version_no} justify="space-between" wrap="nowrap">
                    <Text size="sm">
                      v{v.version_no} · {v.author ?? t("detail.unknownAuthor")}
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

// --- Sandbox trial (one notebook per skill) --------------------------------------------------

function cellText(src: string | string[] | undefined): string {
  return Array.isArray(src) ? src.join("") : (src ?? "");
}

function scoreColor(entry: TrialEntry): string {
  const [a, b] = entry.score.split("/").map(Number);
  if (!b) return "gray";
  const ratio = a / b;
  return ratio >= 0.999 ? "teal" : ratio >= 0.5 ? "yellow" : "red";
}

// Inline **bold** / `code` → React nodes (never raw HTML → no XSS).
function inlineMd(text: string, keyBase: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) nodes.push(<strong key={`${keyBase}-b${i}`}>{tok.slice(2, -2)}</strong>);
    else nodes.push(<Code key={`${keyBase}-c${i}`}>{tok.slice(1, -1)}</Code>);
    last = m.index + tok.length;
    i++;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

// A minimal, safe markdown renderer for notebook markdown cells: headings, lists, paragraphs.
function Markdown({ src }: { src: string }) {
  const lines = src.split("\n");
  const blocks: ReactNode[] = [];
  let list: ReactNode[] = [];
  const flush = (k: string) => {
    if (list.length) {
      blocks.push(
        <List key={`l${k}`} size="sm" spacing={2} withPadding>
          {list}
        </List>,
      );
      list = [];
    }
  };
  lines.forEach((raw, idx) => {
    const line = raw.trimEnd();
    const heading = /^(#{1,4})\s+(.*)/.exec(line);
    const bullet = /^\s*[-*]\s+(.*)/.exec(line);
    const ordered = /^\s*\d+\.\s+(.*)/.exec(line);
    if (heading) {
      flush(`${idx}`);
      const lvl = heading[1].length;
      blocks.push(
        <Text key={idx} fw={700} size={lvl <= 1 ? "lg" : lvl === 2 ? "md" : "sm"} mt={blocks.length ? "xs" : 0}>
          {inlineMd(heading[2], `h${idx}`)}
        </Text>,
      );
    } else if (bullet || ordered) {
      const content = bullet ? bullet[1] : ordered![1];
      list.push(<List.Item key={idx}>{inlineMd(content, `i${idx}`)}</List.Item>);
    } else if (line === "") {
      flush(`${idx}`);
    } else {
      flush(`${idx}`);
      blocks.push(
        <Text key={idx} size="sm">
          {inlineMd(line, `p${idx}`)}
        </Text>,
      );
    }
  });
  flush("end");
  return <Stack gap={4}>{blocks}</Stack>;
}

function Gutter({ label, color }: { label: string; color: string }) {
  return (
    <Text ff="monospace" fw={700} size="10px" c={color} style={{ width: 34, textAlign: "right", flexShrink: 0, paddingTop: 3 }}>
      {label}
    </Text>
  );
}

const MONO_BLOCK = { flex: 1, minWidth: 0, whiteSpace: "pre" as const, overflowX: "auto" as const, fontSize: 12 };

function NotebookCells({ cells }: { cells: NotebookCell[] }) {
  return (
    <Stack gap="sm">
      {cells.map((cell, i) => {
        const src = cellText(cell.source);
        if (cell.cell_type === "markdown") {
          return (
            <Group key={i} align="flex-start" gap="sm" wrap="nowrap">
              <Gutter label="MD" color="dimmed" />
              <div style={{ flex: 1, minWidth: 0 }}>
                <Markdown src={src} />
              </div>
            </Group>
          );
        }
        return (
          <Stack key={i} gap={4}>
            <Group align="flex-start" gap="sm" wrap="nowrap">
              <Gutter label="IN" color="blue" />
              <Code block style={MONO_BLOCK}>
                {src}
              </Code>
            </Group>
            {(cell.outputs ?? []).map((o, j) => (
              <Group key={j} align="flex-start" gap="sm" wrap="nowrap">
                <Gutter label="OUT" color="teal" />
                <Code block style={{ ...MONO_BLOCK, background: "var(--mantine-color-default)" }}>
                  {cellText(o.text)}
                </Code>
              </Group>
            ))}
          </Stack>
        );
      })}
    </Stack>
  );
}

function SandboxTrial({ notebook }: { notebook?: SkillNotebook | null }) {
  const { t } = useI18n();
  const cells = notebook?.notebook?.cells ?? [];
  const entries = notebook?.summary?.entries ?? [];
  return (
    <Card withBorder radius="md" padding="md" mt="md">
      <Group justify="space-between" align="center" mb="xs" wrap="nowrap">
        <Text fw={600}>🧪 {t("trial.title")}</Text>
        {notebook && (
          <Badge color={notebook.stale ? "orange" : "teal"} variant="light">
            {notebook.stale ? t("trial.stale") : t("trial.fresh")}
          </Badge>
        )}
      </Group>
      <Text size="sm" c="dimmed" mb="sm">
        {t("trial.subtitle")}
      </Text>
      {!notebook ? (
        <Alert color="gray" variant="light">
          <Text size="sm">{t("trial.none")}</Text>
          <Text size="xs" c="dimmed" mt={4}>
            {t("trial.noneHint")}
          </Text>
        </Alert>
      ) : (
        <Stack gap="sm">
          <Group gap="md">
            <Text size="xs" c="dimmed">
              {t("trial.scenario", { name: notebook.scenario })}
            </Text>
            {notebook.created_by && (
              <Text size="xs" c="dimmed">
                {t("trial.ranBy", { who: notebook.created_by })}
              </Text>
            )}
          </Group>

          {entries.length > 0 && (
            <div>
              <Text size="sm" fw={600} mb={4}>
                {t("trial.scorecard")}
              </Text>
              <Stack gap="xs">
                {entries.map((e) => (
                  <Paper key={e.label} withBorder radius="sm" p="xs">
                    <Group justify="space-between" mb={4} wrap="nowrap">
                      <Text ff="monospace" size="sm" fw={600}>
                        {e.label}
                      </Text>
                      <Badge color={scoreColor(e)} variant="light">
                        {e.score}
                      </Badge>
                    </Group>
                    <Group gap={4}>
                      {e.passed.map((p) => (
                        <Badge key={p} color="teal" variant="light" size="xs" tt="none" fw={500}>
                          ✓ {p}
                        </Badge>
                      ))}
                      {e.failed.map((f) => (
                        <Badge key={f} color="red" variant="light" size="xs" tt="none" fw={500}>
                          ✗ {f}
                        </Badge>
                      ))}
                    </Group>
                  </Paper>
                ))}
              </Stack>
            </div>
          )}

          {cells.length > 0 && (
            <Accordion variant="contained">
              <Accordion.Item value="notebook">
                <Accordion.Control>
                  {t("trial.viewNotebook")} · {cells.length}
                </Accordion.Control>
                <Accordion.Panel>
                  <NotebookCells cells={cells} />
                </Accordion.Panel>
              </Accordion.Item>
            </Accordion>
          )}

          <Text size="xs" c="dimmed">
            {t("trial.evidence")}
          </Text>
        </Stack>
      )}
    </Card>
  );
}
