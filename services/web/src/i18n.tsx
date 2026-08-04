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
  "app.subtitle": "Developer services platform",
  "nav.catalog": "Catalog",
  "nav.categories": "Categories & ratings",
  "nav.recommendations": "Recommendations",
  "nav.methodology": "Methodology",
  "nav.guide": "Guide",
  "nav.skills": "Skills",
  "nav.reviews": "Reviews",

  // home hub (two service entry points)
  "home.title": "Developer services",
  "home.subtitle": "Two shared services for the team, one sign-in.",
  "home.enter": "Open",
  "home.skills.title": "🧩 SkillHub",
  "home.skills.desc":
    "Team registry of Claude Code skills — catalog, semantic search, quality scores, task-group " +
    "clustering and curator recommendations.",
  "home.skills.stat": "{total} skills · avg {avg}",
  "home.reviews.title": "🔁 Task reviews",
  "home.reviews.desc":
    "Peer-review handoff: submit a deploy-ready task, the lead reviews the branch and sends a " +
    "verdict, feedback flows back — all from Claude Code.",
  "home.reviews.stat": "{open} awaiting action",

  // reviews
  "reviews.title": "Task reviews",
  "reviews.intro":
    "The review board. Developers submit deploy-ready tasks (a pointer to the branch); the lead " +
    "reviews and posts a verdict. Actions happen from Claude Code (submit-for-review / review-inbox " +
    "/ review-status); this page is read-only.",
  "reviews.queueTab": "Review queue",
  "reviews.mineTab": "My submissions",
  "reviews.allTab": "All",
  "reviews.count": "{count} review(s)",
  "reviews.empty": "No reviews here yet.",
  "reviews.by": "by {author}",
  "reviews.reviewer": "reviewer: {who}",
  "reviews.unassigned": "unassigned",
  "reviews.status.submitted": "in review",
  "reviews.status.changes_requested": "changes requested",
  "reviews.status.approved": "approved",
  "reviews.status.done": "done",
  "reviews.task": "Task",
  "reviews.branch": "Branch",
  "reviews.commits": "Commits",
  "reviews.files": "Changed files",
  "reviews.summary": "Summary",
  "reviews.verified": "Verified by author",
  "reviews.thread": "Thread",
  "reviews.notFound": "Review not found.",
  "reviews.event.submit": "submitted",
  "reviews.event.verdict": "verdict",
  "reviews.event.resubmit": "resubmitted",
  "reviews.event.ack": "acknowledged",
  "reviews.usageHint":
    "Act from Claude Code: developers use the submit-for-review / review-status skills; the lead " +
    "runs review-inbox (under /loop). Verdicts and resubmits are not done from this page.",

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
  "catalog.openImprove": "🛠 {n} improve suggestion(s)",
  "catalog.tokensApprox": "~{n} tok",
  "stats.skills": "Skills",
  "stats.evaluated": "Evaluated",
  "stats.avgScore": "Avg score",

  // score
  "score.notScored": "not scored",
  "score.notTrialed": "not trialed",
  "score.effectivenessTitle": "Best sandbox-trial effectiveness ({model})",
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
    "overall is the weighted mean of the dimension scores, computed on the server — so changing a " +
    "weight instantly re-ranks the whole catalog.",
  "meth.weightsEditable": "editable (admin)",
  "meth.saveWeights": "Save weights",
  "meth.resetWeights": "Reset",
  "meth.weightsSaved": "Saved — {n} scores recomputed",
  "meth.weightsError": "Could not save weights",
  "meth.weightsAdminHint":
    "You are an admin: edit the weights below and save. Every skill's overall score recomputes " +
    "from its dimension scores under the new weights.",
  "trial.title": "Sandbox trial",
  "trial.subtitle":
    "The live Claude Code ran this skill against a fake service; the harness scored what it did.",
  "trial.none": "No sandbox trial recorded yet.",
  "trial.noneHint": "Run one with the sandbox-eval skill in Claude Code, then it appears here.",
  "trial.stale": "skill changed since this run — regenerate",
  "trial.fresh": "current",
  "trial.scenario": "Scenario: {name}",
  "trial.ranBy": "run by {who}",
  "trial.scorecard": "Scorecard",
  "trial.viewNotebook": "Run notebook",
  "trial.byModel": "Result grade by model",
  "trial.byModelHint": "panel-median grade /10, capped by the mechanics gate",
  "trial.gateLabel": "gate {v}%",
  "trial.panelMedian": "panel median · judges: {judges}",
  "trial.panel": "Judge panel (blind)",
  "trial.panelHint": "result grade {grade}/10 · median of {n} judges, capped by the mechanics gate",
  "trial.best": "best",
  "trial.viewingModel": "viewing: {model}",
  "trial.notebookFile": "Notebook file",
  "trial.notebookFileHint": "Copy or download the .ipynb and open it in Jupyter / VS Code to run it yourself.",
  "trial.copyIpynb": "Copy .ipynb",
  "trial.downloadIpynb": "Download .ipynb",
  "trial.evidence": "Evidence, not proof — skill runs are non-deterministic.",
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
  "meth.recommendationTitle": "Proposing catalog changes",

  // skill detail
  "detail.notFound": "Skill not found.",
  "detail.meta": "by {author} · v{version} · {format}",
  "detail.whenToUse": "When to use",
  "detail.references": "References",
  "detail.bodyTitle": "SKILL.md — skill body",
  "detail.bodyShowMore": "Show full body",
  "detail.bodyShowLess": "Collapse",
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
  "detail.improvements": "Available improvements ({count})",
  "detail.insertHere": "Suggested addition",

  // auth
  "auth.signIn": "Sign in with GitHub",
  "auth.signOut": "Sign out",
  "auth.gateTitle": "Sign in to SkillHub",
  "auth.gateText": "This SkillHub instance requires sign-in to view the catalog and everything else.",
  "auth.orgDeniedTitle": "Access restricted",
  "auth.orgDenied":
    "This SkillHub instance is limited to the team — GitHub accounts with access to our repository. " +
    "Ask an admin (or the repo owner) to grant your account access, then sign in again.",

  // device flow
  "device.title": "Connect a device",
  "device.intro":
    "Approve the code shown by your Claude Code / MCP to grant it access to SkillHub.",
  "device.needLogin": "Sign in with GitHub first, then approve the code.",
  "device.warningTitle": "Only approve a code you started yourself",
  "device.warning":
    "Approve only if you just started this on your own machine. Never enter a code someone sent you.",
  "device.codeLabel": "Device code",
  "device.approveBtn": "Approve",
  "device.approvedTitle": "Device connected",
  "device.approved":
    "Your device is authorized. Return to your terminal — it will pick up access automatically.",
  "device.error": "Invalid or expired code.",

  // authorship / versions
  "detail.updatedBy": "Updated by {who}",
  "detail.contributors": "Contributors",
  "detail.versionHistory": "Version history",
  "detail.unknownAuthor": "unknown",
};

const ru: Dict = {
  // header / nav
  "app.subtitle": "Платформа сервисов для разработки",
  "nav.catalog": "Каталог",
  "nav.categories": "Категории и рейтинги",
  "nav.recommendations": "Рекомендации",
  "nav.methodology": "Методология",
  "nav.guide": "Инструкция",
  "nav.skills": "Скиллы",
  "nav.reviews": "Ревью",

  // home hub (две точки входа в сервисы)
  "home.title": "Сервисы для разработки",
  "home.subtitle": "Два общих сервиса для команды, один вход.",
  "home.enter": "Открыть",
  "home.skills.title": "🧩 SkillHub",
  "home.skills.desc":
    "Командный реестр скиллов Claude Code — каталог, семантический поиск, оценки качества, " +
    "кластеризация по рабочим группам и рекомендации куратора.",
  "home.skills.stat": "скиллов: {total} · средн. {avg}",
  "home.reviews.title": "🔁 Ревью задач",
  "home.reviews.desc":
    "Передача на ревью: разработчик отправляет готовую задачу (указатель на ветку), лид смотрит " +
    "ветку и выносит вердикт, обратная связь возвращается — всё из Claude Code.",
  "home.reviews.stat": "требуют действия: {open}",

  // reviews
  "reviews.title": "Ревью задач",
  "reviews.intro":
    "Доска ревью. Разработчики отправляют готовые к деплою задачи (указатель на ветку); лид " +
    "смотрит и выносит вердикт. Действия выполняются из Claude Code (submit-for-review / " +
    "review-inbox / review-status); эта страница — только для чтения.",
  "reviews.queueTab": "Очередь ревью",
  "reviews.mineTab": "Мои заявки",
  "reviews.allTab": "Все",
  "reviews.count": "заявок: {count}",
  "reviews.empty": "Здесь пока нет заявок.",
  "reviews.by": "автор: {author}",
  "reviews.reviewer": "ревьюер: {who}",
  "reviews.unassigned": "не назначен",
  "reviews.status.submitted": "на ревью",
  "reviews.status.changes_requested": "нужны правки",
  "reviews.status.approved": "одобрено",
  "reviews.status.done": "закрыто",
  "reviews.task": "Задача",
  "reviews.branch": "Ветка",
  "reviews.commits": "Коммиты",
  "reviews.files": "Изменённые файлы",
  "reviews.summary": "Сводка",
  "reviews.verified": "Проверено автором",
  "reviews.thread": "Тред",
  "reviews.notFound": "Заявка не найдена.",
  "reviews.event.submit": "отправлено",
  "reviews.event.verdict": "вердикт",
  "reviews.event.resubmit": "переотправлено",
  "reviews.event.ack": "подтверждено",
  "reviews.usageHint":
    "Действия — из Claude Code: разработчики используют скиллы submit-for-review / review-status; " +
    "лид запускает review-inbox (под /loop). Вердикты и переотправка не делаются с этой страницы.",

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
  "catalog.openImprove": "🛠 предложений улучшить: {n}",
  "catalog.tokensApprox": "~{n} ток.",
  "stats.skills": "Скиллов",
  "stats.evaluated": "Оценено",
  "stats.avgScore": "Средний балл",

  // score
  "score.notScored": "без оценки",
  "score.notTrialed": "нет прогона",
  "score.effectivenessTitle": "Лучшая эффективность в sandbox-прогоне ({model})",
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
    "overall — это взвешенное среднее баллов по критериям, считается на сервере: изменение веса " +
    "мгновенно переранжирует весь каталог.",
  "meth.weightsEditable": "редактируется (админ)",
  "meth.saveWeights": "Сохранить веса",
  "meth.resetWeights": "Сбросить",
  "meth.weightsSaved": "Сохранено — пересчитано баллов: {n}",
  "meth.weightsError": "Не удалось сохранить веса",
  "meth.weightsAdminHint":
    "Вы админ: измените веса ниже и сохраните. Общий балл каждого скилла пересчитается из его " +
    "покритериальных баллов по новым весам.",
  "trial.title": "Тест в песочнице",
  "trial.subtitle":
    "Живой Claude Code прогнал этот скилл против фейкового сервиса; харнесс оценил, что он сделал.",
  "trial.none": "Прогонов в песочнице ещё не было.",
  "trial.noneHint": "Запустите скилл sandbox-eval в Claude Code — результат появится здесь.",
  "trial.stale": "скилл изменился после прогона — пересоздайте",
  "trial.fresh": "актуально",
  "trial.scenario": "Сценарий: {name}",
  "trial.ranBy": "запустил: {who}",
  "trial.scorecard": "Результаты",
  "trial.viewNotebook": "Ноутбук прогона",
  "trial.byModel": "Оценка результата по моделям",
  "trial.byModelHint": "медиана панели /10, ограничена гейтом по механике",
  "trial.gateLabel": "гейт {v}%",
  "trial.panelMedian": "медиана панели · судьи: {judges}",
  "trial.panel": "Панель судей (вслепую)",
  "trial.panelHint": "оценка результата {grade}/10 · медиана {n} судей, ограничена гейтом по механике",
  "trial.best": "лучшая",
  "trial.viewingModel": "модель: {model}",
  "trial.notebookFile": "Файл ноутбука",
  "trial.notebookFileHint": "Скопируйте или скачайте .ipynb и откройте его в Jupyter / VS Code, чтобы запустить у себя.",
  "trial.copyIpynb": "Скопировать .ipynb",
  "trial.downloadIpynb": "Скачать .ipynb",
  "trial.evidence": "Это свидетельство, а не доказательство — прогоны недетерминированы.",
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
  "meth.recommendationTitle": "Как предлагаются изменения каталога",

  // skill detail
  "detail.notFound": "Скилл не найден.",
  "detail.meta": "автор: {author} · v{version} · {format}",
  "detail.whenToUse": "Когда использовать",
  "detail.references": "Справочные файлы",
  "detail.bodyTitle": "SKILL.md — тело скилла",
  "detail.bodyShowMore": "Показать полностью",
  "detail.bodyShowLess": "Свернуть",
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
  "detail.improvements": "Доступные улучшения ({count})",
  "detail.insertHere": "Предложенное добавление",

  // auth
  "auth.signIn": "Войти через GitHub",
  "auth.signOut": "Выйти",
  "auth.gateTitle": "Вход в SkillHub",
  "auth.gateText": "Этот экземпляр SkillHub требует входа для просмотра каталога и всего остального.",
  "auth.orgDeniedTitle": "Доступ ограничен",
  "auth.orgDenied":
    "Этот экземпляр SkillHub доступен только команде — GitHub-аккаунтам с доступом к нашему " +
    "репозиторию. Попросите админа (или владельца репо) выдать вашему аккаунту доступ и войдите снова.",

  // device flow
  "device.title": "Подключение устройства",
  "device.intro":
    "Подтвердите код, показанный вашим Claude Code / MCP, чтобы дать ему доступ к SkillHub.",
  "device.needLogin": "Сначала войдите через GitHub, затем подтвердите код.",
  "device.warningTitle": "Подтверждайте только код, который запустили сами",
  "device.warning":
    "Подтверждайте, только если вы только что запустили это на своём компьютере. Никогда не вводите код, который вам кто-то прислал.",
  "device.codeLabel": "Код устройства",
  "device.approveBtn": "Подтвердить",
  "device.approvedTitle": "Устройство подключено",
  "device.approved":
    "Устройство авторизовано. Вернитесь в терминал — доступ подхватится автоматически.",
  "device.error": "Неверный или просроченный код.",

  // authorship / versions
  "detail.updatedBy": "Обновил {who}",
  "detail.contributors": "Участники",
  "detail.versionHistory": "История версий",
  "detail.unknownAuthor": "неизвестен",
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
