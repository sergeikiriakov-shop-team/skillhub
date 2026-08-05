import { Badge, Card, Container, Group, Stack, Table, Text, Title } from "@mantine/core";
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

export default function McpMethodology() {
  const { t } = useI18n();
  const { data: r, isLoading } = useQuery({ queryKey: ["mcp-rubric"], queryFn: api.mcpRubric });

  if (isLoading || !r) return <PageLoader />;

  return (
    <Container size="lg">
      <Stack gap="md">
        <Group justify="space-between" align="center">
          <Title order={2}>{t("mcpMeth.title")}</Title>
          <Badge variant="light">
            {t("mcpMeth.version", { version: r.rubric_version })}
          </Badge>
        </Group>
        <Text c="dimmed" size="sm">
          {t("mcpMeth.subtitle")}
        </Text>

        <Section title={t("mcpMeth.instructionsTitle")}>
          <Text size="sm">{r.instructions}</Text>
        </Section>

        <Section title={t("mcpMeth.dimensionsTitle")}>
          <Table verticalSpacing="xs" horizontalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>{t("mcpMeth.dimension")}</Table.Th>
                <Table.Th w={90}>{t("mcpMeth.weight")}</Table.Th>
                <Table.Th>{t("mcpMeth.measures")}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {r.dimensions.map((d) => (
                <Table.Tr key={d.key}>
                  <Table.Td>
                    <Text size="sm" fw={600} ff="monospace">
                      {d.key}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      ×{r.weights[d.key] ?? 0}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{d.description}</Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Section>

        <Section title={t("mcpMeth.calibrationTitle")}>
          <Stack gap="xs">
            {r.calibration.map((band) => (
              <Group key={band.band} align="flex-start" gap="sm" wrap="nowrap">
                <Badge variant="light" w={70} style={{ flexShrink: 0 }}>
                  {band.band}
                </Badge>
                <div>
                  <Text size="sm" fw={600}>
                    {band.label}
                  </Text>
                  <Text size="sm" c="dimmed">
                    {band.meaning}
                  </Text>
                </div>
              </Group>
            ))}
          </Stack>
        </Section>

        <Section title={t("mcpMeth.introspectionTitle")}>
          <Text size="sm">{r.introspection_protocol}</Text>
        </Section>

        <Section title={t("mcpMeth.recommendationTitle")}>
          <Text size="sm">{r.recommendation_strategy}</Text>
        </Section>
      </Stack>
    </Container>
  );
}
