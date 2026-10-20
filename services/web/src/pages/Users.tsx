import {
  Alert,
  Badge,
  Card,
  Container,
  Group,
  Loader,
  Select,
  Stack,
  Switch,
  Table,
  Text,
  Title,
} from "@mantine/core";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import type { AdminUser } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";

const ROLES = ["viewer", "contributor", "evaluator", "admin"];

/** Admin-only user management: the role ladder and the separate lead flag that lets someone sign
 * tasks off on the review board. Your own role is read-only here — the API refuses it (409), so an
 * admin cannot demote themselves out of this page by a slip of the picker. */
export default function Users() {
  const { t } = useI18n();
  const { me } = useAuth();
  const qc = useQueryClient();
  const isAdmin = !!me?.is_admin;

  const users = useQuery({
    queryKey: ["adminUsers"],
    queryFn: () => api.listUsers(),
    enabled: isAdmin,
  });

  const onSaved = (user: AdminUser) => {
    void qc.invalidateQueries({ queryKey: ["adminUsers"] });
    if (user.id === me?.id) void qc.invalidateQueries({ queryKey: ["me"] });
  };
  const setRole = useMutation({
    mutationFn: (v: { id: number; role: string }) => api.setUserRole(v.id, v.role),
    onSuccess: onSaved,
  });
  const setReviewer = useMutation({
    mutationFn: (v: { id: number; isReviewer: boolean }) => api.setReviewer(v.id, v.isReviewer),
    onSuccess: onSaved,
  });

  if (!isAdmin) {
    return (
      <Container size="sm">
        <Alert color="gray" title={t("users.title")}>
          {t("users.adminOnly")}
        </Alert>
      </Container>
    );
  }

  const rows = users.data ?? [];
  const error = setRole.error ?? setReviewer.error ?? users.error;

  return (
    <Container size="lg">
      <Stack gap="md">
        <div>
          <Title order={2}>{t("users.title")}</Title>
          <Text c="dimmed" size="sm">
            {t("users.intro")}
          </Text>
        </div>

        <Card withBorder radius="md" padding="md">
          {users.isLoading ? (
            <Group justify="center" my="lg">
              <Loader />
            </Group>
          ) : (
            <Table.ScrollContainer minWidth={560}>
              <Table verticalSpacing="xs" horizontalSpacing="sm">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{t("users.name")}</Table.Th>
                    <Table.Th w={190}>{t("users.role")}</Table.Th>
                    <Table.Th w={170}>{t("users.lead")}</Table.Th>
                    <Table.Th w={120}>{t("users.since")}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {rows.map((u) => {
                    const self = u.id === me?.id;
                    return (
                      <Table.Tr key={u.id}>
                        <Table.Td>
                          <Group gap={6} wrap="nowrap">
                            <Text size="sm" fw={600}>
                              {u.name}
                            </Text>
                            {self && (
                              <Badge size="xs" variant="light">
                                {t("users.you")}
                              </Badge>
                            )}
                          </Group>
                        </Table.Td>
                        <Table.Td>
                          <Select
                            aria-label={`${u.name}-role`}
                            data={ROLES.map((r) => ({ value: r, label: t(`users.roleName.${r}`) }))}
                            value={u.role}
                            onChange={(value) => {
                              if (value && value !== u.role) setRole.mutate({ id: u.id, role: value });
                            }}
                            disabled={self || (setRole.isPending && setRole.variables?.id === u.id)}
                            allowDeselect={false}
                            size="xs"
                          />
                        </Table.Td>
                        <Table.Td>
                          <Switch
                            aria-label={`${u.name}-lead`}
                            checked={u.is_reviewer}
                            onChange={(event) =>
                              setReviewer.mutate({ id: u.id, isReviewer: event.currentTarget.checked })
                            }
                            disabled={setReviewer.isPending && setReviewer.variables?.id === u.id}
                            label={u.is_reviewer ? t("users.leadOn") : t("users.leadOff")}
                            size="sm"
                          />
                        </Table.Td>
                        <Table.Td>
                          <Text size="xs" c="dimmed">
                            {new Date(u.created_at).toLocaleDateString()}
                          </Text>
                        </Table.Td>
                      </Table.Tr>
                    );
                  })}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
          )}
          {error && (
            <Text c="red" size="sm" mt="xs">
              {String(error)}
            </Text>
          )}
        </Card>

        <Alert variant="light" color="gray">
          {t("users.hint")}
        </Alert>
      </Stack>
    </Container>
  );
}
