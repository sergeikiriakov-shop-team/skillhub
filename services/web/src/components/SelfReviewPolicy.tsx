import { Badge, Button, Card, Group, Select, Stack, Switch, Table, Text, Title } from "@mantine/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { SelfReviewPolicyLane } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";

/** Which catalog skill self-reviews each lane — the team-wide setting Claude Code reads before
 * reviewing a developer's own diff. Admins edit it here (the same shape as the rubric weights:
 * strategy lives in the service, not in each developer's head); everyone else sees it read-only. */
export default function SelfReviewPolicy() {
  const { t } = useI18n();
  const { me } = useAuth();
  const qc = useQueryClient();
  const isAdmin = !!me?.is_admin;

  const policy = useQuery({ queryKey: ["selfReviewPolicy"], queryFn: () => api.selfReviewPolicy() });
  // Only needed to populate the admin's picker — skip the fetch for everyone else.
  const skills = useQuery({
    queryKey: ["skills"],
    queryFn: () => api.listSkills(),
    enabled: isAdmin,
  });

  const [edited, setEdited] = useState<Record<string, SelfReviewPolicyLane>>({});
  useEffect(() => {
    const lanes = policy.data?.lanes ?? [];
    setEdited(Object.fromEntries(lanes.map((l) => [l.lane, l])));
  }, [policy.data]);

  const save = useMutation({
    mutationFn: (lane: SelfReviewPolicyLane) =>
      api.updateSelfReviewPolicy(lane.lane, lane.skill, lane.required),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["selfReviewPolicy"] }),
  });

  const lanes = policy.data?.lanes ?? [];
  if (policy.isLoading || lanes.length === 0) return null;

  const options = (skills.data ?? []).map((s) => ({ value: s.name, label: s.name }));
  const changed = (lane: SelfReviewPolicyLane) => {
    const draft = edited[lane.lane];
    return !!draft && (draft.skill !== lane.skill || draft.required !== lane.required);
  };

  return (
    <Card withBorder radius="md" padding="md">
      <Group justify="space-between" align="center" mb={4}>
        <Title order={4}>{t("selfReview.policyTitle")}</Title>
        {isAdmin && (
          <Badge variant="light" color="grape">
            {t("meth.weightsEditable")}
          </Badge>
        )}
      </Group>
      <Text size="xs" c="dimmed" mb="sm">
        {t("selfReview.policyIntro")}
      </Text>

      <Table verticalSpacing="xs" horizontalSpacing="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th w={140}>{t("selfReview.lane")}</Table.Th>
            <Table.Th>{t("selfReview.skill")}</Table.Th>
            <Table.Th w={220}>{t("selfReview.required")}</Table.Th>
            {isAdmin && <Table.Th w={110} />}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {lanes.map((lane) => {
            const draft = edited[lane.lane] ?? lane;
            return (
              <Table.Tr key={lane.lane}>
                <Table.Td>
                  <Text size="sm" fw={600}>
                    {t(`selfReview.lane.${lane.lane}`)}
                  </Text>
                </Table.Td>
                <Table.Td>
                  {isAdmin ? (
                    <Select
                      aria-label={lane.lane}
                      data={options}
                      value={draft.skill}
                      onChange={(value) =>
                        setEdited((prev) => ({ ...prev, [lane.lane]: { ...draft, skill: value } }))
                      }
                      placeholder={t("selfReview.notSet")}
                      searchable
                      clearable
                      size="xs"
                    />
                  ) : lane.skill ? (
                    <Text size="sm">{lane.skill}</Text>
                  ) : (
                    <Text size="sm" c="dimmed">
                      {t("selfReview.notSet")}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  {isAdmin ? (
                    <Switch
                      aria-label={`${lane.lane}-required`}
                      checked={draft.required}
                      onChange={(event) =>
                        setEdited((prev) => ({
                          ...prev,
                          [lane.lane]: { ...draft, required: event.currentTarget.checked },
                        }))
                      }
                      size="sm"
                      label={draft.required ? t("selfReview.requiredShort") : t("selfReview.optional")}
                    />
                  ) : (
                    <Badge variant="light" color={lane.required ? "orange" : "gray"}>
                      {lane.required ? t("selfReview.requiredShort") : t("selfReview.optional")}
                    </Badge>
                  )}
                </Table.Td>
                {isAdmin && (
                  <Table.Td>
                    <Button
                      size="xs"
                      disabled={!changed(lane)}
                      loading={save.isPending && save.variables?.lane === lane.lane}
                      onClick={() => save.mutate(draft)}
                    >
                      {t("selfReview.save")}
                    </Button>
                  </Table.Td>
                )}
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>

      {!isAdmin && (
        <Text size="xs" c="dimmed" mt="xs">
          {t("selfReview.adminOnly")}
        </Text>
      )}
      {save.isError && (
        <Stack gap={0} mt="xs">
          <Text c="red" size="sm">
            {String(save.error)}
          </Text>
        </Stack>
      )}
    </Card>
  );
}
