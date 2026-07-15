import { Badge, Card, Code, Container, Group, Stack, Table, Text, Title } from "@mantine/core";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { api } from "../api";
import PageLoader from "../components/PageLoader";
import { useI18n } from "../i18n";

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
  const { t } = useI18n();
  const { data: r, isLoading } = useQuery({ queryKey: ["rubric"], queryFn: api.rubric });

  if (isLoading || !r) {
    return <PageLoader />;
  }

  return (
    <Container size="md">
      <Stack gap="lg">
        <div>
          <Group gap="sm" align="center">
            <Title order={2}>{t("meth.title")}</Title>
            <Badge variant="light" size="lg">
              {t("meth.rubricBadge", { v: r.rubric_version })}
            </Badge>
          </Group>
          <Text c="dimmed" size="sm">
            {t("meth.intro")}
          </Text>
        </div>

        <Section title={t("meth.reviewerInstructions")}>
          <Text size="sm">{r.instructions}</Text>
        </Section>

        <Section title={t("meth.dimensionsTitle")}>
          <Table verticalSpacing="xs" horizontalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t("meth.dimension")}</Table.Th>
                <Table.Th>{t("meth.measures")}</Table.Th>
                <Table.Th ta="right">{t("meth.weight")}</Table.Th>
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
            {t("meth.overallNote")}
          </Text>
        </Section>

        <Section title={t("meth.calibrationTitle")}>
          <Table verticalSpacing="xs" horizontalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th w={64}>{t("meth.band")}</Table.Th>
                <Table.Th w={130}>{t("meth.label")}</Table.Th>
                <Table.Th>{t("meth.meaning")}</Table.Th>
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

        <Section title={t("meth.categorizationTitle")}>
          <Text size="sm" mb="md">
            {r.categorization_rules}
          </Text>
          <Title order={5} mb="xs">
            {t("meth.taxonomy")}
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

        <Section title={t("meth.selectionTitle")}>
          <Text size="sm">{r.selection_strategy}</Text>
        </Section>

        <Section title={t("meth.synthesisTitle")}>
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
                {t("meth.synthesisPromptNote")}
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
