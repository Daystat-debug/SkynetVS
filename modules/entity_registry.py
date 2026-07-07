from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, Iterable


@dataclass(frozen=True)
class AliasMatch:
    code: str
    score: float


@dataclass(frozen=True)
class AppSpec:
    code: str
    title: str
    aliases: tuple[str, ...]
    open_command: tuple[str, ...] = ()
    image_names: tuple[str, ...] = ()
    title_patterns: tuple[str, ...] = ()
    close_strategy: str = "normal"


@dataclass(frozen=True)
class SiteSpec:
    code: str
    title: str
    aliases: tuple[str, ...]
    url: str


@dataclass(frozen=True)
class FolderSpec:
    code: str
    title: str
    aliases: tuple[str, ...]
    path_kind: str


@dataclass(frozen=True)
class SettingsSectionSpec:
    code: str
    title: str
    aliases: tuple[str, ...]
    uri: str


APP_REGISTRY: Dict[str, AppSpec] = {
    "notepad": AppSpec(
        code="notepad",
        title="блокнот",
        aliases=(
            "блокнот",
            "notepad",
            "нотпад",
        ),
        open_command=("notepad.exe",),
        image_names=("notepad.exe",),
        title_patterns=("блокнот", "notepad"),
    ),
    "calc": AppSpec(
        code="calc",
        title="калькулятор",
        aliases=(
            "калькулятор",
            "calculator",
            "calc",
            "кальк",
        ),
        open_command=("calc.exe",),
        image_names=("CalculatorApp.exe", "calc.exe"),
        title_patterns=("калькулятор", "calculator"),
    ),
    "chrome": AppSpec(
        code="chrome",
        title="браузер",
        aliases=(
            "хром",
            "chrome",
            "гугл хром",
            "google chrome",
            "браузер",
            "гугл браузер",
            "google браузер",
            "интернет браузер",
        ),
        open_command=("cmd", "/c", "start", "chrome"),
        image_names=("chrome.exe",),
        title_patterns=("chrome", "google chrome", "хром"),
    ),
    "discord": AppSpec(
        code="discord",
        title="дискорд",
        aliases=(
            "дискорд",
            "discord",
            "дискомфорт",
            "де скоро",
            "диск орды",
            "дискорда",
        ),
        open_command=("cmd", "/c", "start", "discord"),
        image_names=("Discord.exe", "Update.exe"),
        title_patterns=("discord", "дискорд"),
    ),
    "explorer": AppSpec(
        code="explorer",
        title="проводник",
        aliases=(
            "проводник",
            "проводник windows",
            "проводник виндовс",
            "explorer",
            "file explorer",
            "файловый менеджер",
        ),
        open_command=("explorer.exe",),
        image_names=("explorer.exe",),
        title_patterns=(),
        close_strategy="explorer_windows_only",
    ),
}


SITE_REGISTRY: Dict[str, SiteSpec] = {
    "youtube": SiteSpec(
        code="youtube",
        title="ютуб",
        aliases=("ютуб", "youtube", "you tube"),
        url="https://www.youtube.com",
    ),
    "google": SiteSpec(
        code="google",
        title="гугл",
        aliases=("гугл", "google"),
        url="https://www.google.com",
    ),
    "github": SiteSpec(
        code="github",
        title="гитхаб",
        aliases=(
            "гитхаб",
            "github",
            "git hub",
            "гит хаб",
            "гед хаб",
            "гид хаб",
            "гиды хаб",
            "github.com",
        ),
        url="https://github.com",
    ),
    "gmail": SiteSpec(
        code="gmail",
        title="gmail",
        aliases=("gmail", "джимейл", "почта gmail", "gmail почта"),
        url="https://mail.google.com",
    ),
    "chatgpt": SiteSpec(
        code="chatgpt",
        title="chatgpt",
        aliases=(
            "chatgpt",
            "чат gpt",
            "чат джипити",
            "чат жпт",
            "чат гпт",
            "чат джип ти",
            "чат джип идти",
            "чат же пяти",
            "чоджи пяти",
            "чат гпу",
            "чат гбдд",
        ),
        url="https://chatgpt.com",
    ),
    "habr": SiteSpec(
        code="habr",
        title="хабр",
        aliases=("хабр", "habr", "хабр ру", "habr.ru"),
        url="https://habr.com",
    ),
    "yandex": SiteSpec(
        code="yandex",
        title="яндекс",
        aliases=("яндекс", "yandex", "яндекс ру", "yandex.ru"),
        url="https://yandex.ru",
    ),
    "vk": SiteSpec(
        code="vk",
        title="вк",
        aliases=("вк", "vk", "вконтакте", "vk.com", "вк точка ком"),
        url="https://vk.com",
    ),
    "openai": SiteSpec(
        code="openai",
        title="openai",
        aliases=("openai", "open ai", "openai.com", "опен аи"),
        url="https://openai.com",
    ),
}


FOLDER_REGISTRY: Dict[str, FolderSpec] = {
    "downloads": FolderSpec(
        code="downloads",
        title="загрузки",
        aliases=("загрузки", "загрузок", "папка загрузки", "папка загрузок", "downloads", "download"),
        path_kind="downloads",
    ),
    "desktop": FolderSpec(
        code="desktop",
        title="рабочий стол",
        aliases=("рабочий стол", "desktop", "стол"),
        path_kind="desktop",
    ),
    "documents": FolderSpec(
        code="documents",
        title="документы",
        aliases=("документы", "мои документы", "папка документы", "documents", "docs"),
        path_kind="documents",
    ),
    "pictures": FolderSpec(
        code="pictures",
        title="картинки",
        aliases=("картинки", "изображения", "фото", "папка картинки", "pictures", "images"),
        path_kind="pictures",
    ),
}


SETTINGS_SECTION_REGISTRY: Dict[str, SettingsSectionSpec] = {
    "system": SettingsSectionSpec(
        code="system",
        title="настройки",
        aliases=("настройки", "параметры", "система"),
        uri="ms-settings:",
    ),
    "sound": SettingsSectionSpec(
        code="sound",
        title="настройки звука",
        aliases=("настройки звука", "параметры звука", "звук", "аудио"),
        uri="ms-settings:sound",
    ),
    "network": SettingsSectionSpec(
        code="network",
        title="настройки сети",
        aliases=("настройки сети", "параметры сети", "сеть", "интернет", "wi-fi", "вайфай"),
        uri="ms-settings:network",
    ),
    "bluetooth": SettingsSectionSpec(
        code="bluetooth",
        title="настройки bluetooth",
        aliases=("настройки bluetooth", "настройки блютуз", "bluetooth", "блютуз"),
        uri="ms-settings:bluetooth",
    ),
    "display": SettingsSectionSpec(
        code="display",
        title="настройки экрана",
        aliases=("настройки экрана", "параметры экрана", "экран", "дисплей"),
        uri="ms-settings:display",
    ),
}


def normalize_entity_text(text: str) -> str:
    return " ".join((text or "").lower().split())


def compact_entity_text(text: str) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", "", normalize_entity_text(text))


def _specs_to_aliases(specs: Dict[str, object]) -> Dict[str, list[str]]:
    result: Dict[str, list[str]] = {}

    for code, spec in specs.items():
        aliases = getattr(spec, "aliases", ())
        result[code] = list(aliases)

    return result


def _titles_from_specs(specs: Dict[str, object]) -> Dict[str, str]:
    result: Dict[str, str] = {}

    for code, spec in specs.items():
        result[code] = str(getattr(spec, "title", code) or code)

    return result


APP_ALIASES: Dict[str, list[str]] = _specs_to_aliases(APP_REGISTRY)
APP_TITLES: Dict[str, str] = _titles_from_specs(APP_REGISTRY)

SITE_ALIASES: Dict[str, list[str]] = _specs_to_aliases(SITE_REGISTRY)
SITE_TITLES: Dict[str, str] = _titles_from_specs(SITE_REGISTRY)
SITE_URLS: Dict[str, str] = {
    code: spec.url
    for code, spec in SITE_REGISTRY.items()
}

FOLDER_ALIASES: Dict[str, list[str]] = _specs_to_aliases(FOLDER_REGISTRY)
FOLDER_TITLES: Dict[str, str] = _titles_from_specs(FOLDER_REGISTRY)

SETTINGS_SECTION_ALIASES: Dict[str, list[str]] = _specs_to_aliases(SETTINGS_SECTION_REGISTRY)
SETTINGS_SECTION_TITLES: Dict[str, str] = _titles_from_specs(SETTINGS_SECTION_REGISTRY)


def _iter_alias_hits(
    text_norm: str,
    text_compact: str,
    aliases: Iterable[str],
) -> Iterable[int]:
    for alias in aliases:
        alias_norm = normalize_entity_text(alias)
        alias_compact = compact_entity_text(alias)

        if alias_norm and alias_norm in text_norm:
            yield len(alias_compact)
            continue

        if alias_compact and alias_compact in text_compact:
            yield len(alias_compact)


def find_alias_match(
    text: str,
    alias_map: Dict[str, list[str]],
    *,
    fuzzy: bool = False,
    min_ratio: float = 0.84,
    min_margin: float = 0.08,
) -> AliasMatch | None:
    """
    Ищет сущность по alias-map.

    Сначала ищет exact-ish совпадения и выбирает самый длинный alias.
    Это важно для случаев:
      - "настройки" vs "настройки звука";
      - "звук" vs "настройки звука";
      - "vk" vs "vk.com".

    Fuzzy включается только явно.
    """
    text_norm = normalize_entity_text(text)
    text_compact = compact_entity_text(text)

    best_exact_code = ""
    best_exact_len = -1

    for code, aliases in alias_map.items():
        for hit_len in _iter_alias_hits(text_norm, text_compact, aliases):
            if hit_len > best_exact_len:
                best_exact_len = hit_len
                best_exact_code = code

    if best_exact_code:
        return AliasMatch(
            code=best_exact_code,
            score=1.0,
        )

    if not fuzzy:
        return None

    best_code = ""
    best_score = 0.0
    second_score = 0.0

    for code, aliases in alias_map.items():
        local_best = 0.0

        for alias in aliases:
            alias_compact = compact_entity_text(alias)
            if not alias_compact:
                continue

            score = SequenceMatcher(None, text_compact, alias_compact).ratio()

            if score > local_best:
                local_best = score

        if local_best > best_score:
            second_score = best_score
            best_score = local_best
            best_code = code
        elif local_best > second_score:
            second_score = local_best

    if best_score >= min_ratio and (best_score - second_score) >= min_margin:
        return AliasMatch(
            code=best_code,
            score=best_score,
        )

    return None


def match_app(text: str, *, fuzzy: bool = False) -> AliasMatch | None:
    return find_alias_match(text, APP_ALIASES, fuzzy=fuzzy)


def match_app_code(text: str, *, fuzzy: bool = False) -> str | None:
    match = match_app(text, fuzzy=fuzzy)
    return match.code if match else None


def match_site(text: str, *, fuzzy: bool = False) -> AliasMatch | None:
    return find_alias_match(text, SITE_ALIASES, fuzzy=fuzzy)


def match_site_code(text: str, *, fuzzy: bool = False) -> str | None:
    match = match_site(text, fuzzy=fuzzy)
    return match.code if match else None


def match_folder(text: str, *, fuzzy: bool = False) -> AliasMatch | None:
    return find_alias_match(text, FOLDER_ALIASES, fuzzy=fuzzy)


def match_folder_code(text: str, *, fuzzy: bool = False) -> str | None:
    match = match_folder(text, fuzzy=fuzzy)
    return match.code if match else None


def match_settings_section(text: str, *, fuzzy: bool = False) -> AliasMatch | None:
    return find_alias_match(text, SETTINGS_SECTION_ALIASES, fuzzy=fuzzy)


def match_settings_section_code(text: str, *, fuzzy: bool = False) -> str | None:
    match = match_settings_section(text, fuzzy=fuzzy)
    return match.code if match else None


def get_app_title(code: str) -> str:
    return APP_TITLES.get(code, code)


def get_site_title(code: str) -> str:
    return SITE_TITLES.get(code, code)


def get_site_url(code: str) -> str:
    return SITE_URLS.get(code, "")


def get_folder_title(code: str) -> str:
    return FOLDER_TITLES.get(code, code)


def get_settings_section_title(code: str) -> str:
    return SETTINGS_SECTION_TITLES.get(code, code)


def get_settings_section_uri(code: str) -> str:
    spec = SETTINGS_SECTION_REGISTRY.get(code)
    if spec is None:
        return "ms-settings:"
    return spec.uri


def get_folder_path_kind(code: str) -> str:
    spec = FOLDER_REGISTRY.get(code)
    if spec is None:
        return ""
    return spec.path_kind


def get_app_open_command(code: str) -> tuple[str, ...]:
    spec = APP_REGISTRY.get(code)
    if spec is None:
        return ()
    return spec.open_command


def get_app_image_names(code: str) -> tuple[str, ...]:
    spec = APP_REGISTRY.get(code)
    if spec is None:
        return ()
    return spec.image_names


def get_app_title_patterns(code: str) -> tuple[str, ...]:
    spec = APP_REGISTRY.get(code)
    if spec is None:
        return ()
    return spec.title_patterns


def get_app_close_strategy(code: str) -> str:
    spec = APP_REGISTRY.get(code)
    if spec is None:
        return "normal"
    return spec.close_strategy