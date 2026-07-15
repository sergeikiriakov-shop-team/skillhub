import {
  Anchor,
  AppShell,
  Avatar,
  Badge,
  Button,
  Group,
  Menu,
  SegmentedControl,
  Text,
  Title,
} from "@mantine/core";
import { Link, NavLink, Route, Routes } from "react-router-dom";
import Catalog from "./pages/Catalog";
import Categories from "./pages/Categories";
import DeviceApprove from "./pages/DeviceApprove";
import Guide from "./pages/Guide";
import Methodology from "./pages/Methodology";
import Recommendations from "./pages/Recommendations";
import SkillDetail from "./pages/SkillDetail";
import { useI18n } from "./i18n";
import type { Lang } from "./i18n";
import { useAuth } from "./auth";

function NavItem({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      end
      style={({ isActive }) => ({
        textDecoration: "none",
        fontWeight: isActive ? 700 : 500,
        color: isActive ? "var(--mantine-color-blue-6)" : "var(--mantine-color-dimmed)",
        fontSize: "var(--mantine-font-size-sm)",
      })}
    >
      {label}
    </NavLink>
  );
}

function LanguageToggle() {
  const { lang, setLang } = useI18n();
  return (
    <SegmentedControl
      size="xs"
      value={lang}
      onChange={(v) => setLang(v as Lang)}
      data={[
        { label: "EN", value: "en" },
        { label: "RU", value: "ru" },
      ]}
    />
  );
}

function AuthControl() {
  const { t } = useI18n();
  const { me, isAuthenticated, isLoading, login, logout } = useAuth();
  if (isLoading) {
    return null;
  }
  if (!isAuthenticated) {
    return (
      <Button size="xs" variant="light" onClick={() => login()}>
        {t("auth.signIn")}
      </Button>
    );
  }
  const label = me?.name || me?.email || "user";
  return (
    <Menu shadow="md" width={220} position="bottom-end">
      <Menu.Target>
        <Button size="xs" variant="subtle" leftSection={<Avatar size={20} radius="xl" color="blue" />}>
          {label}
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>
          <Group justify="space-between" gap="xs" wrap="nowrap">
            <Text size="xs" truncate>
              {me?.email}
            </Text>
            <Badge size="xs" variant="light">
              {me?.role}
            </Badge>
          </Group>
        </Menu.Label>
        <Menu.Divider />
        <Menu.Item onClick={() => void logout()}>{t("auth.signOut")}</Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}

export default function App() {
  const { t } = useI18n();
  return (
    <AppShell header={{ height: 60 }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group wrap="nowrap">
            <Anchor component={Link} to="/" underline="never">
              <Title order={3}>🧩 SkillHub</Title>
            </Anchor>
            <Text c="dimmed" size="sm" visibleFrom="md">
              {t("app.subtitle")}
            </Text>
          </Group>
          <Group gap="lg" wrap="nowrap">
            <Group gap="lg" wrap="nowrap">
              <NavItem to="/" label={t("nav.catalog")} />
              <NavItem to="/categories" label={t("nav.categories")} />
              <NavItem to="/recommendations" label={t("nav.recommendations")} />
              <NavItem to="/methodology" label={t("nav.methodology")} />
              <NavItem to="/guide" label={t("nav.guide")} />
            </Group>
            <LanguageToggle />
            <AuthControl />
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Main>
        <Routes>
          <Route path="/" element={<Catalog />} />
          <Route path="/categories" element={<Categories />} />
          <Route path="/recommendations" element={<Recommendations />} />
          <Route path="/methodology" element={<Methodology />} />
          <Route path="/guide" element={<Guide />} />
          <Route path="/device" element={<DeviceApprove />} />
          <Route path="/skills/:id" element={<SkillDetail />} />
        </Routes>
      </AppShell.Main>
    </AppShell>
  );
}
