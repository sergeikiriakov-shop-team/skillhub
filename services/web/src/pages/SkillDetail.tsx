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
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { ScoreBadge, ScoreBreakdown } from "../components/Score";
import { useI18n } from "../i18n";

export default function SkillDetail() {
  const { t } = useI18n();
  const { id } = useParams();
  const skillId = Number(id);

  const { data: skill, isLoading } = useQuery({
    queryKey: ["skill", skillId],
    queryFn: () => api.getSkill(skillId),
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
          </Grid.Col>
        </Grid>
      </Stack>
    </Container>
  );
}
