import {
  Alert,
  Anchor,
  AppShell,
  Avatar,
  Badge,
  Button,
  Card,
  Container,
  Group,
  Menu,
  SegmentedControl,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import Catalog from "./pages/Catalog";
import Categories from "./pages/Categories";
import DeviceApprove from "./pages/DeviceApprove";
import Guide from "./pages/Guide";
import Home from "./pages/Home";
import McpCatalog from "./pages/McpCatalog";
import McpDetail from "./pages/McpDetail";
import McpMethodology from "./pages/McpMethodology";
import McpRecommendations from "./pages/McpRecommendations";
import Methodology from "./pages/Methodology";
import Recommendations from "./pages/Recommendations";
import Reviews from "./pages/Reviews";
import ReviewDetail from "./pages/ReviewDetail";
import SkillDetail from "./pages/SkillDetail";
import PageLoader from "./components/PageLoader";
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

// A top-level service tab (Skills / Reviews). Active across the whole section, not just an exact path.
function ServiceLink({ to, label, active }: { to: string; label: string; active: boolean }) {
  return (
    <Anchor
      component={Link}
      to={to}
      underline="never"
      fw={active ? 700 : 500}
      c={active ? "blue.6" : "dimmed"}
      size="sm"
    >
      {label}
    </Anchor>
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
            <Group gap={4} wrap="nowrap">
              {me?.is_reviewer && (
                <Badge size="xs" variant="light" color="grape">
                  lead
                </Badge>
              )}
              <Badge size="xs" variant="light">
                {me?.role}
              </Badge>
            </Group>
          </Group>
        </Menu.Label>
        <Menu.Divider />
        <Menu.Item onClick={() => void logout()}>{t("auth.signOut")}</Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}

function LoginGate() {
  const { t } = useI18n();
  const { login } = useAuth();
  return (
    <Container size="xs" mt={80}>
      <Card withBorder radius="md" padding="xl">
        <Stack align="center" gap="md">
          <Title order={3}>{t("auth.gateTitle")}</Title>
          <Text c="dimmed" ta="center" size="sm">
            {t("auth.gateText")}
          </Text>
          <Button onClick={() => login()}>{t("auth.signIn")}</Button>
        </Stack>
      </Card>
    </Container>
  );
}

export default function App() {
  const { t } = useI18n();
  const { isAuthenticated, isLoading, readsRequireAuth } = useAuth();
  const location = useLocation();
  const path = location.pathname;
  const loginError = new URLSearchParams(location.search).get("login_error");
  // Gate everything behind login when the server closes reads — except the device-approval page,
  // which handles its own sign-in and must stay reachable for the MCP flow.
  const gated = readsRequireAuth && !isAuthenticated && path !== "/device";

  const isReviews = path === "/reviews" || path.startsWith("/reviews/");
  // The MCP section lives under /servers, NOT /mcp: nginx prefix-matches `location /mcp` and
  // proxies the whole /mcp* space to the MCP protocol container, which would shadow these routes.
  const isMcp = path === "/servers" || path.startsWith("/servers/");
  // Skills is the catch-all section, so it must exclude every sibling service explicitly.
  const isSkills = !isReviews && !isMcp && path !== "/" && path !== "/device";

  return (
    <AppShell header={{ height: 60 }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group wrap="nowrap" gap="lg">
            <Anchor component={Link} to="/" underline="never">
              <Title order={3}>🧰 Dev Services</Title>
            </Anchor>
            {!gated && (
              <Group gap="md" wrap="nowrap">
                <ServiceLink to="/skills" label={t("nav.skills")} active={isSkills} />
                <ServiceLink to="/servers" label={t("nav.mcp")} active={isMcp} />
                <ServiceLink to="/reviews" label={t("nav.reviews")} active={isReviews} />
              </Group>
            )}
          </Group>
          <Group gap="lg" wrap="nowrap">
            {!gated && isSkills && (
              <Group gap="lg" wrap="nowrap" visibleFrom="lg">
                <NavItem to="/skills" label={t("nav.catalog")} />
                <NavItem to="/categories" label={t("nav.categories")} />
                <NavItem to="/recommendations" label={t("nav.recommendations")} />
                <NavItem to="/methodology" label={t("nav.methodology")} />
                <NavItem to="/guide" label={t("nav.guide")} />
              </Group>
            )}
            {!gated && isMcp && (
              <Group gap="lg" wrap="nowrap" visibleFrom="lg">
                <NavItem to="/servers" label={t("nav.catalog")} />
                <NavItem to="/servers/recommendations" label={t("nav.recommendations")} />
                <NavItem to="/servers/methodology" label={t("nav.methodology")} />
              </Group>
            )}
            <LanguageToggle />
            <AuthControl />
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Main>
        {loginError === "org" && !isAuthenticated && (
          <Container size="sm" mb="md">
            <Alert color="red" title={t("auth.orgDeniedTitle")}>
              {t("auth.orgDenied")}
            </Alert>
          </Container>
        )}
        {isLoading ? (
          <PageLoader />
        ) : gated ? (
          <LoginGate />
        ) : (
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/skills" element={<Catalog />} />
            <Route path="/skills/:id" element={<SkillDetail />} />
            <Route path="/categories" element={<Categories />} />
            <Route path="/recommendations" element={<Recommendations />} />
            <Route path="/methodology" element={<Methodology />} />
            <Route path="/guide" element={<Guide />} />
            {/* Static MCP segments before the dynamic :id (v6 ranks them anyway; explicit is clearer). */}
            <Route path="/servers" element={<McpCatalog />} />
            <Route path="/servers/recommendations" element={<McpRecommendations />} />
            <Route path="/servers/methodology" element={<McpMethodology />} />
            <Route path="/servers/:id" element={<McpDetail />} />
            <Route path="/reviews" element={<Reviews />} />
            <Route path="/reviews/:id" element={<ReviewDetail />} />
            <Route path="/device" element={<DeviceApprove />} />
          </Routes>
        )}
      </AppShell.Main>
    </AppShell>
  );
}
