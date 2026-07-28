import { Badge, Button, Card, Code, Container, Group, NumberInput, Stack, Table, Text, Title } from "@mantine/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { api } from "../api";
import type { Rubric } from "../api";
import { useAuth } from "../auth";
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

/** Scoring dimensions & weights. Admins get editable weights (server recomputes every overall
 * score on save); everyone else sees the current weights read-only. */
function WeightsEditor({ r }: { r: Rubric }) {
  const { t } = useI18n();
  const { me } = useAuth();
  const qc = useQueryClient();
  const isAdmin = !!me?.is_admin;

  const [edited, setEdited] = useState<Record<string, number>>(r.weights);
  useEffect(() => setEdited(r.weights), [r.weights]);

  const save = useMutation({
    mutationFn: (weights: Record<string, number>) => api.updateRubricWeights(weights),
    onSuccess: () => {
      // Scores are server-recomputed, so refresh everything that shows a score/ranking.
      for (const key of ["rubric", "skills", "stats", "categories"]) {
        qc.invalidateQueries({ queryKey: [key] });
      }
    },
  });

  const dirty = r.dimensions.some((d) => (edited[d.key] ?? 0) !== (r.weights[d.key] ?? 0));

  return (
    <Card withBorder radius="md" padding="md">
      <Group justify="space-between" align="center" mb="xs">
        <Title order={4}>{t("meth.dimensionsTitle")}</Title>
        {isAdmin && (
          <Badge variant="light" color="grape">
            {t("meth.weightsEditable")}
          </Badge>
        )}
      </Group>
      {isAdmin && (
        <Text size="xs" c="dimmed" mb="sm">
          {t("meth.weightsAdminHint")}
        </Text>
      )}
      <Table verticalSpacing="xs" horizontalSpacing="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{t("meth.dimension")}</Table.Th>
            <Table.Th>{t("meth.measures")}</Table.Th>
            <Table.Th ta="right" w={120}>
              {t("meth.weight")}
            </Table.Th>
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
                {isAdmin ? (
                  <NumberInput
                    aria-label={d.key}
                    value={edited[d.key] ?? 0}
                    onChange={(v) =>
                      setEdited((prev) => ({ ...prev, [d.key]: typeof v === "number" ? v : Number(v) || 0 }))
                    }
                    min={0}
                    step={0.5}
                    decimalScale={2}
                    w={100}
                    ml="auto"
                    size="xs"
                  />
                ) : (
                  <Badge variant="light" color={(r.weights[d.key] ?? 1) >= 2 ? "teal" : "gray"}>
                    ×{r.weights[d.key] ?? 1}
                  </Badge>
                )}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      <Text size="xs" c="dimmed" mt="xs">
        {t("meth.overallNote")}
      </Text>
      {isAdmin && (
        <Group mt="md" gap="sm" align="center">
          <Button
            size="xs"
            disabled={!dirty}
            loading={save.isPending}
            onClick={() => save.mutate(edited)}
          >
            {t("meth.saveWeights")}
          </Button>
          <Button size="xs" variant="default" disabled={!dirty} onClick={() => setEdited(r.weights)}>
            {t("meth.resetWeights")}
          </Button>
          {save.isSuccess && !dirty && (
            <Text c="teal" size="sm">
              {t("meth.weightsSaved", { n: save.data?.rescored ?? 0 })}
            </Text>
          )}
          {save.isError && (
            <Text c="red" size="sm">
              {t("meth.weightsError")}
            </Text>
          )}
        </Group>
      )}
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

        <WeightsEditor r={r} />

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
