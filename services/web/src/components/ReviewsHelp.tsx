import { Accordion, Button, Code, CopyButton, Group, List, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { useLocalStorage } from "@mantine/hooks";
import { useI18n } from "../i18n";
import type { TFunc } from "../i18n";
import ReviewDocsLink from "./ReviewDocsLink";

// The Reviews page's own how-to: the one-time setup and the everyday loop for both sides of the
// flow, as phrases and commands to paste into Claude Code, plus the rules people trip over most.
// Which sections are open is remembered per browser, so a returning user can fold it away once.

const OPEN_KEY = "skillhub-reviews-help";
const TIP_COUNT = 6;

interface Step {
  text: string;
  snippets?: string[];
}

function Snippet({ value, t }: { value: string; t: TFunc }) {
  return (
    <Group gap="xs" wrap="nowrap" align="flex-start" mt={4}>
      <Code block style={{ whiteSpace: "pre-wrap", flex: 1, minWidth: 0 }}>
        {value}
      </Code>
      <CopyButton value={value}>
        {({ copied, copy }) => (
          <Button size="compact-xs" variant="light" color={copied ? "teal" : "gray"} onClick={copy}>
            {copied ? t("common.copied") : t("common.copy")}
          </Button>
        )}
      </CopyButton>
    </Group>
  );
}

function Steps({ title, steps, t }: { title: string; steps: Step[]; t: TFunc }) {
  return (
    <div>
      <Title order={5} mb="xs">
        {title}
      </Title>
      <Stack gap="sm">
        {steps.map((step, i) => (
          <div key={i}>
            <Text size="sm">
              <b>{i + 1}.</b> {step.text}
            </Text>
            {step.snippets?.map((s) => <Snippet key={s} value={s} t={t} />)}
          </div>
        ))}
      </Stack>
    </div>
  );
}

export default function ReviewsHelp() {
  const { t } = useI18n();
  const [open, setOpen] = useLocalStorage<string[]>({
    key: OPEN_KEY,
    defaultValue: ["howto", "tips"],
  });
  // Commands name the exact host the page is viewed at, like the developer guide does.
  const origin = typeof window !== "undefined" ? window.location.origin : "https://<your-server>";

  return (
    <Accordion multiple variant="contained" radius="md" value={open} onChange={setOpen}>
      <Accordion.Item value="howto">
        <Accordion.Control>
          <Text fw={600}>{t("reviews.howto.title")}</Text>
        </Accordion.Control>
        <Accordion.Panel>
          <Stack gap="lg">
            <Text size="sm" c="dimmed">
              {t("reviews.howto.intro")} <ReviewDocsLink label={t("reviews.docsMore")} />
            </Text>
            <Steps
              t={t}
              title={t("reviews.howto.setup")}
              steps={[
                {
                  text: t("reviews.howto.setupMcp"),
                  snippets: [`claude mcp add --transport http --scope user skillhub ${origin}/mcp`],
                },
                {
                  text: t("reviews.howto.setupSkills"),
                  snippets: [t("reviews.howto.setupSkillsDev"), t("reviews.howto.setupSkillsLead")],
                },
              ]}
            />
            <SimpleGrid cols={{ base: 1, md: 2 }} spacing="xl">
              <Steps
                t={t}
                title={t("reviews.howto.dev")}
                steps={[
                  { text: t("reviews.howto.dev1") },
                  { text: t("reviews.howto.dev2"), snippets: [t("reviews.howto.dev2Phrase")] },
                  { text: t("reviews.howto.dev3"), snippets: [t("reviews.howto.dev3Phrase")] },
                  { text: t("reviews.howto.dev4"), snippets: ["/loop 15m review-status"] },
                ]}
              />
              <Steps
                t={t}
                title={t("reviews.howto.lead")}
                steps={[
                  { text: t("reviews.howto.lead1"), snippets: ["/loop 30m review-board"] },
                  {
                    text: t("reviews.howto.lead2"),
                    snippets: [t("reviews.howto.lead2Show"), t("reviews.howto.lead2Diff")],
                  },
                  {
                    text: t("reviews.howto.lead3"),
                    snippets: [t("reviews.howto.lead3Approve"), t("reviews.howto.lead3Return")],
                  },
                ]}
              />
            </SimpleGrid>
          </Stack>
        </Accordion.Panel>
      </Accordion.Item>

      <Accordion.Item value="tips">
        <Accordion.Control>
          <Text fw={600}>{t("reviews.tips.title")}</Text>
        </Accordion.Control>
        <Accordion.Panel>
          <List size="sm" spacing="xs">
            {Array.from({ length: TIP_COUNT }, (_, i) => (
              <List.Item key={i}>{t(`reviews.tips.${i + 1}`)}</List.Item>
            ))}
          </List>
          <Text size="sm" mt="sm">
            <ReviewDocsLink label={t("reviews.tips.more")} />
          </Text>
        </Accordion.Panel>
      </Accordion.Item>
    </Accordion>
  );
}
