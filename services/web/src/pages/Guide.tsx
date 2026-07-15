import { Card, Code, Container, List, Stack, Text, Title } from "@mantine/core";
import { useI18n } from "../i18n";
import type { Lang } from "../i18n";

// The developer guide is long-form prose, authored in full for each language rather than
// assembled from short dictionary keys. It reads the active language from the shared toggle.

type Block =
  | { kind: "p"; text: string }
  | { kind: "list"; items: string[] }
  | { kind: "code"; text: string };

interface Section {
  heading: string;
  blocks: Block[];
}

interface GuideContent {
  title: string;
  intro: string;
  sections: Section[];
}

const MCP_JSON = `{
  "mcpServers": {
    "skillhub": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "SKILLHUB_URL=https://<your-server>",
        "-e", "SKILLHUB_TOKEN_FILE=/data/token",
        "-v", "skillhub-mcp-token:/data",
        "skillhub-mcp"
      ]
    }
  }
}`;

const en: GuideContent = {
  title: "Developer guide",
  intro:
    "SkillHub is a shared registry of Claude Code skills for the team. The service stores skills, " +
    "their local embeddings (for search and duplicate detection) and their quality evaluations — " +
    "but it never calls an LLM itself. Your Claude Code does the reasoning (evaluating, " +
    "categorizing, synthesizing) against one shared strategy and submits results back over the API.",
  sections: [
    {
      heading: "1. The dashboard (read-only)",
      blocks: [
        { kind: "p", text: "This portal only shows data; you change things from Claude Code / the API." },
        {
          kind: "list",
          items: [
            "Catalog — browse every skill and search by meaning (semantic search), not just by name.",
            "Categories & ratings — skills grouped by a broad category and a narrow task group, with a leaderboard and the synthesized “ideal” skills.",
            "Recommendations — proposed catalog changes (synthesize / split / merge / dedup / delete), each with a ready-to-run action.",
            "Methodology — the exact rubric every evaluator uses. Read it to understand the scores.",
          ],
        },
      ],
    },
    {
      heading: "2. Sign in & roles",
      blocks: [
        {
          kind: "p",
          text: "Reading is open to everyone — no sign-in. To write, sign in with Google (top-right). " +
            "Any Google account works; you start as a viewer. Roles, ascending:",
        },
        {
          kind: "list",
          items: [
            "viewer — read only (same as signed-out).",
            "contributor — may upload/import skills.",
            "evaluator — may submit evaluations.",
            "admin — manages users and roles.",
          ],
        },
        {
          kind: "p",
          text: "An admin promotes you from viewer to contributor/evaluator once you've signed in.",
        },
      ],
    },
    {
      heading: "3. Connect SkillHub to your Claude Code (MCP)",
      blocks: [
        { kind: "p", text: "Build the MCP image once:" },
        { kind: "code", text: "DOCKER_BUILDKIT=0 docker build -t skillhub-mcp services/mcp" },
        {
          kind: "p",
          text: "Add this to your .mcp.json (set SKILLHUB_URL to the server). The volume caches your " +
            "token so you authorize only once per machine:",
        },
        { kind: "code", text: MCP_JSON },
        {
          kind: "p",
          text: "Reads need nothing. The first time you use a write tool (or run the `authenticate` " +
            "tool), the server prints a verification link + code: open it, approve at /device (signing " +
            "in with Google), and the token is cached to the volume. Then just talk to Claude Code.",
        },
      ],
    },
    {
      heading: "4. Upload / import a skill",
      blocks: [
        { kind: "p", text: "With a contributor+ token, tell Claude Code:" },
        { kind: "code", text: "Import this SKILL.md into SkillHub" },
        {
          kind: "p",
          text: "It calls upload_skill (raw SKILL.md text + optional references). The service parses, " +
            "embeds and stores it; a new version is created only when the content changes.",
        },
      ],
    },
    {
      heading: "5. Evaluate skills",
      blocks: [
        { kind: "p", text: "With an evaluator token, ask:" },
        { kind: "code", text: "Evaluate the pending SkillHub skills" },
        {
          kind: "p",
          text: "Claude Code fetches the work queue (unevaluated skills), fetches the shared rubric, " +
            "scores each skill against it, and submits the assessment back. Because the rubric lives in " +
            "the service, every developer scores by the same algorithm — see the Methodology page.",
        },
      ],
    },
    {
      heading: "6. Install a skill into your Claude Code",
      blocks: [
        {
          kind: "p",
          text: "Found a skill you want to use? On its page, copy the install phrase (the button next to " +
            "“Install into Claude Code”), or just ask Claude Code:",
        },
        { kind: "code", text: 'Install the "beliani-db-schema" skill from SkillHub into my project' },
        {
          kind: "p",
          text: "Claude Code fetches the skill and writes SKILL.md (plus any references) into " +
            ".claude/skills/<name>/ for this project, or ~/.claude/skills/<name>/ for all your projects. " +
            "It restarts / refreshes to pick up the new skill.",
        },
      ],
    },
  ],
};

const ru: GuideContent = {
  title: "Инструкция для разработчиков",
  intro:
    "SkillHub — это общий реестр скиллов Claude Code для команды. Сервис хранит скиллы, их локальные " +
    "эмбеддинги (для поиска и обнаружения дублей) и оценки качества — но сам никогда не вызывает LLM. " +
    "Всю «умную» работу (оценка, категоризация, синтез) делает ваш Claude Code по единой общей " +
    "стратегии и присылает результаты обратно через API.",
  sections: [
    {
      heading: "1. Дашборд (только для чтения)",
      blocks: [
        {
          kind: "p",
          text: "Этот портал только показывает данные; изменения вы вносите из Claude Code / через API.",
        },
        {
          kind: "list",
          items: [
            "Каталог — просмотр всех скиллов и поиск по смыслу (семантический), а не только по названию.",
            "Категории и рейтинги — скиллы сгруппированы по широкой категории и узкой рабочей группе, с общим рейтингом и синтезированными «эталонными» скиллами.",
            "Рекомендации — предложенные изменения каталога (синтез / разделение / объединение / дедупликация / удаление), у каждого есть готовое к запуску действие.",
            "Методология — точная рубрика, по которой оценивает каждый ревьюер. Прочитайте её, чтобы понимать оценки.",
          ],
        },
      ],
    },
    {
      heading: "2. Вход и роли",
      blocks: [
        {
          kind: "p",
          text: "Чтение открыто всем — без входа. Чтобы писать, войдите через Google (справа вверху). " +
            "Подойдёт любой Google-аккаунт; вы начинаете как viewer. Роли по возрастанию прав:",
        },
        {
          kind: "list",
          items: [
            "viewer — только чтение (как без входа).",
            "contributor — может загружать/импортировать скиллы.",
            "evaluator — может отправлять оценки.",
            "admin — управляет пользователями и ролями.",
          ],
        },
        {
          kind: "p",
          text: "Админ повышает вас с viewer до contributor/evaluator после того, как вы вошли.",
        },
      ],
    },
    {
      heading: "3. Подключение SkillHub к вашему Claude Code (MCP)",
      blocks: [
        { kind: "p", text: "Один раз соберите образ MCP:" },
        { kind: "code", text: "DOCKER_BUILDKIT=0 docker build -t skillhub-mcp services/mcp" },
        {
          kind: "p",
          text: "Добавьте это в свой .mcp.json (укажите SKILLHUB_URL сервера). Том кэширует токен, " +
            "чтобы авторизоваться только один раз на машине:",
        },
        { kind: "code", text: MCP_JSON },
        {
          kind: "p",
          text: "Для чтения ничего не нужно. При первом вызове пишущего инструмента (или запустив " +
            "инструмент `authenticate`) сервер выдаст ссылку и код: откройте её, подтвердите на /device " +
            "(войдя через Google) — токен закэшируется в том. Дальше просто общайтесь с Claude Code.",
        },
      ],
    },
    {
      heading: "4. Загрузка / импорт скилла",
      blocks: [
        { kind: "p", text: "С токеном contributor+ скажите Claude Code:" },
        { kind: "code", text: "Импортируй этот SKILL.md в SkillHub" },
        {
          kind: "p",
          text: "Он вызовет upload_skill (текст SKILL.md + при необходимости references). Сервис распарсит, " +
            "построит эмбеддинг и сохранит скилл; новая версия создаётся только при изменении содержимого.",
        },
      ],
    },
    {
      heading: "5. Оценка скиллов",
      blocks: [
        { kind: "p", text: "С токеном evaluator попросите:" },
        { kind: "code", text: "Оцени неоценённые скиллы в SkillHub" },
        {
          kind: "p",
          text: "Claude Code возьмёт очередь работы (неоценённые скиллы), загрузит общую рубрику, оценит " +
            "каждый скилл по ней и отправит оценку обратно. Поскольку рубрика хранится в сервисе, все " +
            "разработчики оценивают по одному алгоритму — см. страницу «Методология».",
        },
      ],
    },
    {
      heading: "6. Установка скилла в свой Claude Code",
      blocks: [
        {
          kind: "p",
          text: "Нашли нужный скилл? На его странице скопируйте фразу установки (кнопка рядом с " +
            "«Установка в Claude Code») или просто попросите Claude Code:",
        },
        { kind: "code", text: "Установи скилл «beliani-db-schema» из SkillHub в мой проект" },
        {
          kind: "p",
          text: "Claude Code скачает скилл и запишет SKILL.md (и все references) в .claude/skills/<name>/ " +
            "для этого проекта или в ~/.claude/skills/<name>/ для всех ваших проектов. Затем " +
            "перезапустится / обновится, чтобы подхватить новый скилл.",
        },
      ],
    },
  ],
};

const CONTENT: Record<Lang, GuideContent> = { en, ru };

function renderBlock(block: Block, i: number) {
  if (block.kind === "p") {
    return (
      <Text key={i} size="sm">
        {block.text}
      </Text>
    );
  }
  if (block.kind === "list") {
    return (
      <List key={i} size="sm" spacing="xs">
        {block.items.map((item, j) => (
          <List.Item key={j}>{item}</List.Item>
        ))}
      </List>
    );
  }
  return (
    <Code key={i} block style={{ whiteSpace: "pre-wrap" }}>
      {block.text}
    </Code>
  );
}

export default function Guide() {
  const { lang } = useI18n();
  const content = CONTENT[lang];

  return (
    <Container size="md">
      <Stack gap="lg">
        <div>
          <Title order={2}>{content.title}</Title>
          <Text c="dimmed" size="sm" mt="xs">
            {content.intro}
          </Text>
        </div>

        {content.sections.map((section) => (
          <Card key={section.heading} withBorder radius="md" padding="md">
            <Title order={4} mb="sm">
              {section.heading}
            </Title>
            <Stack gap="sm">{section.blocks.map(renderBlock)}</Stack>
          </Card>
        ))}
      </Stack>
    </Container>
  );
}
