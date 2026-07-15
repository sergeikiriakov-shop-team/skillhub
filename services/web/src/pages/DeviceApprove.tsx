import { Alert, Button, Container, Stack, Text, TextInput, Title } from "@mantine/core";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import PageLoader from "../components/PageLoader";

type Status = "idle" | "working" | "done" | "error";

export default function DeviceApprove() {
  const { t } = useI18n();
  const { isAuthenticated, isLoading, login } = useAuth();
  const [params] = useSearchParams();
  const [code, setCode] = useState(params.get("user_code") ?? "");
  const [status, setStatus] = useState<Status>("idle");

  if (isLoading) {
    return <PageLoader size="xs" />;
  }

  const approve = async () => {
    setStatus("working");
    try {
      await api.deviceApprove(code.trim());
      setStatus("done");
    } catch {
      setStatus("error");
    }
  };

  return (
    <Container size="xs">
      <Stack gap="md">
        <div>
          <Title order={2}>{t("device.title")}</Title>
          <Text c="dimmed" size="sm" mt="xs">
            {t("device.intro")}
          </Text>
        </div>

        {!isAuthenticated ? (
          <>
            <Text size="sm">{t("device.needLogin")}</Text>
            <Button onClick={() => login(`/device?user_code=${encodeURIComponent(code)}`)}>
              {t("auth.signIn")}
            </Button>
          </>
        ) : status === "done" ? (
          <Alert color="green" title={t("device.approvedTitle")}>
            {t("device.approved")}
          </Alert>
        ) : (
          <Stack gap="md">
            <Alert color="yellow" title={t("device.warningTitle")}>
              {t("device.warning")}
            </Alert>
            <TextInput
              label={t("device.codeLabel")}
              placeholder="XXXX-XXXX"
              value={code}
              onChange={(e) => setCode(e.currentTarget.value)}
            />
            {status === "error" && <Alert color="red">{t("device.error")}</Alert>}
            <Button onClick={approve} loading={status === "working"} disabled={!code.trim()}>
              {t("device.approveBtn")}
            </Button>
          </Stack>
        )}
      </Stack>
    </Container>
  );
}
