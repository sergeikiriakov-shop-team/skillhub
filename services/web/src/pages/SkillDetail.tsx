import {
  Accordion,
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Container,
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
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { ScoreBadge, ScoreBreakdown } from "../components/Score";

export default function SkillDetail() {
  const { id } = useParams();
  const skillId = Number(id);
  const navigate = useNavigate();

  const { data: skill, isLoading } = useQuery({
    queryKey: ["skill", skillId],
    queryFn: () => api.getSkill(skillId),
  });
  const remove = useMutation({
    mutationFn: () => api.deleteSkill(skillId),
    onSuccess: () => navigate("/"),
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
        <Alert color="red">Skill not found.</Alert>
      </Container>
    );
  }

  const evalr = skill.latest_evaluation;

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
              by {skill.author ?? "unknown"} · v{skill.version_no} · {skill.source_format}
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
          <Button color="red" variant="subtle" onClick={() => remove.mutate()}>
            Delete
          </Button>
        </Group>

        <Grid>
          {/* Left: content */}
          <Grid.Col span={{ base: 12, md: 8 }}>
            {skill.trigger_text && (
              <Alert color="indigo" variant="light" title="When to use" mb="md">
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
                  References
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

          {/* Right: evaluation + similar */}
          <Grid.Col span={{ base: 12, md: 4 }}>
            <Card withBorder radius="md" padding="md">
              <Text fw={600} mb="sm">
                Quality evaluation
              </Text>
              {evalr ? (
                <Stack gap="sm">
                  <ScoreBreakdown scores={evalr.scores} />
                  <Divider />
                  {evalr.strengths.length > 0 && (
                    <div>
                      <Text size="sm" fw={600} c="teal">
                        Strengths
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
                        Weaknesses
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
                    {evalr.model} · rubric v{evalr.rubric_version}
                  </Text>
                </Stack>
              ) : (
                <Text size="sm" c="dimmed">
                  Not evaluated yet — run the SkillHub skill in Claude Code to score it.
                </Text>
              )}
            </Card>

            <Card withBorder radius="md" padding="md" mt="md">
              <Text fw={600} mb="sm">
                Similar skills
              </Text>
              {skill.similar.length === 0 ? (
                <Text size="sm" c="dimmed">
                  No neighbours found.
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
