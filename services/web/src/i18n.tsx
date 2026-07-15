// Lightweight, dependency-free i18n for the dashboard: a language context (persisted to
// localStorage) plus a `t(key, vars)` lookup over EN/RU dictionaries. Only the static UI chrome
// is translated — data from the API (skill names, descriptions, rubric text) stays as stored.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

export type Lang = "en" | "ru";

const STORAGE_KEY = "skillhub-lang";

type Dict = Record<string, string>;

const en: Dict = {
  // header / nav
  "app.subtitle": "Claude Code skills registry (read-only dashboard)",
  "nav.catalog": "Catalog",
  "nav.categories": "Categories & ratings",
  "nav.recommendations": "Recommendations",
  "nav.methodology": "Methodology",
  "nav.guide": "Guide",

  // common
  "common.copy": "Copy",
  "common.copied": "Copied",

  // catalog
  "catalog.title": "Skill catalog",
  "catalog.searchResults": "Semantic search results",
  "catalog.count": "{count} skill(s)",
  "catalog.searchPlaceholder": "Search by meaning (e.g. 'run SQL against production safely')",
  "catalog.allCategories": "All categories",
  "catalog.empty":
    "No skills yet — import some via Claude Code (the SkillHub skill) or the seed command.",
  "catalog.by": "by {author}",
  "catalog.unknownAuthor": "unknown",
  "catalog.match": "{pct}% match",
  "catalog.noDescription": "No description.",
  "stats.skills": "Skills",
  "stats.evaluated": "Evaluated",
  "stats.avgScore": "Avg score",

  // score
  "score.notScored": "not scored",
  "dim.clarity": "Clarity",
  "dim.trigger_quality": "Trigger quality",
  "dim.completeness": "Completeness",
  "dim.reusability": "Reusability",
  "dim.safety": "Safety",
  "dim.structure": "Structure",

  // categories
  "categories.title": "Categories & ratings",
  "categories.intro":
    "The output of the registry. Skills are grouped on two levels — a broad category, then the " +
    "narrow task group (their specific job). Within a task group with more than one skill (a real " +
    '"same job" competition) the ★ marks the top-rated one. Synthesized ideals are listed ' +
    "separately and excluded from the competition and the averages.",
  "categories.synthTitle": "✦ Synthesized ideals",
  "categories.synthIntro":
    "Skills the registry generated itself — each merges the best of one task group via the stored " +
    "synthesis algorithm. The nested list shows the source skills it was built from.",
  "categories.mergedFrom": "merged from",
  "categories.leaderboard": "Overall leaderboard",
  "categories.noScored": "No scored skills yet.",
  "categories.count": "{count} skill(s)",
  "categories.avg": "avg {v}",
  "categories.noneInCategory": "No skills in this category yet.",
  "categories.competing": "{count} competing",
  "table.rank": "#",
  "table.skill": "Skill",
  "table.author": "Author",
  "table.score": "Score",
  "badge.synthesized": "✦ synthesized",
  "badge.best": "★ best",
  "badge.stale": "stale v{v}",
  "badge.staleTitle": "scored under an older rubric",
  "group.ungrouped": "ungrouped",

  // recommendations
  "rec.title": "Recommendations",
  "rec.open": "{count} open",
  "rec.intro":
    "Proposed catalog changes the registry has surfaced — synthesize, split, merge, dedup or " +
    "delete. Each carries a ready-to-run action a developer can pick up and execute in their own " +
    "Claude Code; the service keeps them so nothing is lost between sessions.",
  "rec.empty": "No recommendations yet.",
  "rec.runThis": "Run this (in your Claude Code):",
  "rec.scope": "scope: {v}",

  // methodology
  "meth.title": "How skills are evaluated",
  "meth.rubricBadge": "rubric v{v}",
  "meth.intro":
    "The single, shared evaluation strategy — stored in the service and fetched by every " +
    "developer's Claude Code (GET /api/rubric) before it scores a skill, so the algorithm is " +
    "identical for everyone. The service itself runs no LLM; it stores this strategy and the results.",
  "meth.reviewerInstructions": "Reviewer instructions",
  "meth.dimensionsTitle": "Scoring dimensions & weights",
  "meth.dimension": "Dimension",
  "meth.measures": "What it measures",
  "meth.weight": "Weight",
  "meth.overallNote":
    "overall is a holistic 0-10 judgement weighted by these factors — trigger quality and " +
    "completeness count roughly double.",
  "meth.calibrationTitle": "Score calibration (0–10)",
  "meth.band": "Band",
  "meth.label": "Label",
  "meth.meaning": "Meaning",
  "meth.categorizationTitle": "Categorization",
  "meth.taxonomy": "Taxonomy",
  "meth.selectionTitle": "Choosing the best in a group",
  "meth.synthesisTitle": "Synthesizing the ideal skill",
  "meth.synthesisPromptNote":
    "Synthesis prompt (filled in per group and run by every developer's Claude Code):",

  // skill detail
  "detail.notFound": "Skill not found.",
  "detail.meta": "by {author} · v{version} · {format}",
  "detail.whenToUse": "When to use",
  "detail.references": "References",
  "detail.qualityEval": "Quality evaluation",
  "detail.strengths": "Strengths",
  "detail.weaknesses": "Weaknesses",
  "detail.notEvaluated": "Not evaluated yet — run the SkillHub skill in Claude Code to score it.",
  "detail.evalMeta": "{model} · rubric v{version}",
  "detail.similar": "Similar skills",
  "detail.noNeighbours": "No neighbours found.",
  "detail.installTitle": "Install into Claude Code",
  "detail.installHint": "With the SkillHub skill or MCP connected, tell your Claude Code:",
  "detail.installPhrase": 'Install the "{name}" skill from SkillHub into my project',
  "detail.installNote":
    "Claude Code fetches it and writes SKILL.md (+ references) into .claude/skills/{name}/.",
};

const ru: Dict = {
  // header / nav
  "app.subtitle": "Реестр скиллов Claude Code (дашборд только для чтения)",
  "nav.catalog": "Каталог",
  "nav.categories": "Категории и рейтинги",
  "nav.recommendations": "Рекомендации",
  "nav.methodology": "Методология",
  "nav.guide": "Инструкция",

  // common
  "common.copy": "Копировать",
  "common.copied": "Скопировано",

  // catalog
  "catalog.title": "Каталог скиллов",
  "catalog.searchResults": "Результаты семантического поиска",
  "catalog.count": "скиллов: {count}",
  "catalog.searchPlaceholder": "Поиск по смыслу (например, «безопасно выполнить SQL на проде»)",
  "catalog.allCategories": "Все категории",
  "catalog.empty":
    "Пока нет скиллов — импортируйте их через Claude Code (скилл SkillHub) или командой seed.",
  "catalog.by": "автор: {author}",
  "catalog.unknownAuthor": "неизвестен",
  "catalog.match": "совпадение {pct}%",
  "catalog.noDescription": "Без описания.",
  "stats.skills": "Скиллов",
  "stats.evaluated": "Оценено",
  "stats.avgScore": "Средний балл",

  // score
  "score.notScored": "без оценки",
  "dim.clarity": "Ясность",
  "dim.trigger_quality": "Качество триггера",
  "dim.completeness": "Полнота",
  "dim.reusability": "Переиспользуемость",
  "dim.safety": "Безопасность",
  "dim.structure": "Структура",

  // categories
  "categories.title": "Категории и рейтинги",
  "categories.intro":
    "Итог работы реестра. Скиллы сгруппированы на двух уровнях — широкая категория, затем узкая " +
    "рабочая группа (их конкретная задача). Внутри рабочей группы, где больше одного скилла " +
    "(настоящая конкуренция «за одну работу»), ★ отмечает лучший по оценке. Синтезированные " +
    "эталоны показаны отдельно и исключены из конкуренции и из средних значений.",
  "categories.synthTitle": "✦ Синтезированные эталоны",
  "categories.synthIntro":
    "Скиллы, которые реестр сгенерировал сам — каждый объединяет лучшее из одной рабочей группы " +
    "по сохранённому алгоритму синтеза. Вложенный список показывает исходные скиллы, из которых он собран.",
  "categories.mergedFrom": "собрано из",
  "categories.leaderboard": "Общий рейтинг",
  "categories.noScored": "Пока нет оценённых скиллов.",
  "categories.count": "скиллов: {count}",
  "categories.avg": "средн. {v}",
  "categories.noneInCategory": "В этой категории пока нет скиллов.",
  "categories.competing": "конкурируют: {count}",
  "table.rank": "#",
  "table.skill": "Скилл",
  "table.author": "Автор",
  "table.score": "Балл",
  "badge.synthesized": "✦ синтезирован",
  "badge.best": "★ лучший",
  "badge.stale": "устар. v{v}",
  "badge.staleTitle": "оценён по старой рубрике",
  "group.ungrouped": "без группы",

  // recommendations
  "rec.title": "Рекомендации",
  "rec.open": "открытых: {count}",
  "rec.intro":
    "Предложенные изменения каталога, которые выявил реестр — синтезировать, разделить, объединить, " +
    "убрать дубли или удалить. У каждого есть готовое к запуску действие, которое разработчик может " +
    "взять и выполнить в своём Claude Code; сервис хранит их, чтобы ничего не терялось между сессиями.",
  "rec.empty": "Пока нет рекомендаций.",
  "rec.runThis": "Выполните это (в своём Claude Code):",
  "rec.scope": "область: {v}",

  // methodology
  "meth.title": "Как оцениваются скиллы",
  "meth.rubricBadge": "рубрика v{v}",
  "meth.intro":
    "Единая общая стратегия оценки — хранится в сервисе и загружается в Claude Code каждого " +
    "разработчика (GET /api/rubric) перед оценкой скилла, так что алгоритм у всех одинаковый. Сам " +
    "сервис не вызывает LLM; он хранит эту стратегию и результаты.",
  "meth.reviewerInstructions": "Инструкции ревьюеру",
  "meth.dimensionsTitle": "Критерии оценки и веса",
  "meth.dimension": "Критерий",
  "meth.measures": "Что измеряет",
  "meth.weight": "Вес",
  "meth.overallNote":
    "overall — это целостная оценка 0-10, взвешенная по этим факторам: качество триггера и полнота " +
    "весят примерно вдвое больше.",
  "meth.calibrationTitle": "Калибровка баллов (0–10)",
  "meth.band": "Диапазон",
  "meth.label": "Метка",
  "meth.meaning": "Значение",
  "meth.categorizationTitle": "Категоризация",
  "meth.taxonomy": "Таксономия",
  "meth.selectionTitle": "Выбор лучшего в группе",
  "meth.synthesisTitle": "Синтез идеального скилла",
  "meth.synthesisPromptNote":
    "Промпт синтеза (заполняется по группе и выполняется в Claude Code каждого разработчика):",

  // skill detail
  "detail.notFound": "Скилл не найден.",
  "detail.meta": "автор: {author} · v{version} · {format}",
  "detail.whenToUse": "Когда использовать",
  "detail.references": "Справочные файлы",
  "detail.qualityEval": "Оценка качества",
  "detail.strengths": "Сильные стороны",
  "detail.weaknesses": "Слабые стороны",
  "detail.notEvaluated": "Ещё не оценён — запустите скилл SkillHub в Claude Code, чтобы оценить.",
  "detail.evalMeta": "{model} · рубрика v{version}",
  "detail.similar": "Похожие скиллы",
  "detail.noNeighbours": "Соседей не найдено.",
  "detail.installTitle": "Установка в Claude Code",
  "detail.installHint": "Подключив скилл SkillHub или MCP, скажите своему Claude Code:",
  "detail.installPhrase": "Установи скилл «{name}» из SkillHub в мой проект",
  "detail.installNote":
    "Claude Code скачает его и запишет SKILL.md (+ references) в .claude/skills/{name}/.",
};

const DICTS: Record<Lang, Dict> = { en, ru };

export type TFunc = (key: string, vars?: Record<string, string | number>) => string;

interface I18nContextValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: TFunc;
}

const I18nContext = createContext<I18nContextValue | null>(null);

function readInitialLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "en" || saved === "ru") return saved;
  } catch {
    // localStorage may be unavailable; fall through to the default.
  }
  return "en";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(readInitialLang);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      // ignore persistence failures
    }
    document.documentElement.lang = lang;
  }, [lang]);

  const t = useCallback<TFunc>(
    (key, vars) => {
      let value = DICTS[lang][key] ?? DICTS.en[key] ?? key;
      if (vars) {
        for (const [name, replacement] of Object.entries(vars)) {
          value = value.split(`{${name}}`).join(String(replacement));
        }
      }
      return value;
    },
    [lang],
  );

  const ctx = useMemo(() => ({ lang, setLang: setLangState, t }), [lang, t]);
  return <I18nContext.Provider value={ctx}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useI18n must be used within an I18nProvider");
  }
  return ctx;
}
