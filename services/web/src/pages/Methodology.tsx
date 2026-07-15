import {
  Badge,
  Card,
  Code,
  Container,
  Group,
  Loader,
  Stack,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { api } from "../api";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card withBorder radius="md" padding="md">
      <Title order={4} mb="xs">
        {title}
      </Title>
      {children}
    </Card>
  );
}

export default function Methodology() {
  const { data: r, isLoading } = useQuery({ queryKey: ["rubric"], queryFn: api.rubric });

  if (isLoading || !r) {
    return (
      <Container size="md">
        <Group justify="center" mt="xl">
          <Loader />
        </Group>
      </Container>
    );
  }

  return (
    <Container size="md">
      <Stack gap="lg">
        <div>
          <Group gap="sm" align="center">
            <Title order={2}>How skills are evaluated</Title>
            <Badge variant="light" size="lg">
              rubric v{r.rubric_version}
            </Badge>
          </Group>
          <Text c="dimmed" size="sm">
            The single, shared evaluation strategy — stored in the service and fetched by every
            developer&apos;s Claude Code (<Code>GET /api/rubric</Code>) before it scores a skill, so
            the algorithm is identical for everyone. The service itself runs no LLM; it stores this
            strategy and the results.
          </Text>
        </div>

        <Section title="Reviewer instructions">
          <Text size="sm">{r.instructions}</Text>
        </Section>

        <Section title="Scoring dimensions & weights">
          <Table verticalSpacing="xs" horizontalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Dimension</Table.Th>
                <Table.Th>What it measures</Table.Th>
                <Table.Th ta="right">Weight</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {r.dimensions.map((d) => (
                <Table.Tr key={d.key}>
                  <Table.Td>
                    <Code>{d.key}</Code>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{d.description}</Text>
                  </Table.Td>
                  <Table.Td ta="right">
                    <Badge
                      variant="light"
                      color={(r.weights[d.key] ?? 1) >= 2 ? "teal" : "gray"}
                    >
                      ×{r.weights[d.key] ?? 1}
                    </Badge>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          <Text size="xs" c="dimmed" mt="xs">
            <b>overall</b> is a holistic 0-10 judgement weighted by these factors — trigger quality
            and completeness count roughly double.
          </Text>
        </Section>

        <Section title="Score calibration (0–10)">
          <Table verticalSpacing="xs" horizontalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th w={64}>Band</Table.Th>
                <Table.Th w={130}>Label</Table.Th>
                <Table.Th>Meaning</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {r.calibration.map((c) => (
                <Table.Tr key={c.band}>
                  <Table.Td>
                    <Code>{c.band}</Code>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" fw={600}>
                      {c.label}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{c.meaning}</Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Section>

        <Section title="Categorization">
          <Text size="sm" mb="md">
            {r.categorization_rules}
          </Text>
          <Title order={5} mb="xs">
            Taxonomy
          </Title>
          <Stack gap="xs">
            {r.categories.map((c) => (
              <Group key={c.key} gap="sm" align="flex-start" wrap="nowrap">
                <Badge variant="light" miw={130} style={{ flexShrink: 0 }}>
                  {c.label}
                </Badge>
                <Text size="sm" c="dimmed">
                  {c.description}
                </Text>
              </Group>
            ))}
          </Stack>
        </Section>

        <Section title="Choosing the best in a group">
          <Text size="sm">{r.selection_strategy}</Text>
        </Section>

        <Section title="Synthesizing the ideal skill">
          <Text size="sm" mb={r.synthesis_algorithm.length ? "md" : 0}>
            {r.synthesis_strategy}
          </Text>
          {r.synthesis_algorithm.length > 0 && (
            <Stack gap="xs" mb="md">
              {r.synthesis_algorithm.map((s) => (
                <Group key={s.step} gap="sm" align="flex-start" wrap="nowrap">
                  <Badge variant="light" color="grape" style={{ flexShrink: 0 }}>
                    {s.step}
                  </Badge>
                  <Text size="sm">{s.detail}</Text>
                </Group>
              ))}
            </Stack>
          )}
          {r.synthesis_prompt && (
            <>
              <Text size="xs" c="dimmed" mb={4}>
                Synthesis prompt (filled in per group and run by every developer&apos;s Claude Code):
              </Text>
              <Code block style={{ whiteSpace: "pre-wrap" }}>
                {r.synthesis_prompt}
              </Code>
            </>
          )}
        </Section>
      </Stack>
    </Container>
  );
}
