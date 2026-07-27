"""Chat persona labels and system-prompt fragments (ported from Lite)."""

from __future__ import annotations

from dataclasses import dataclass

ID_WIKI_MAINTAINER = "wiki_maintainer"
ID_SOFTWARE_ENGINEER = "software_engineer"
ID_BUSINESS_ANALYST = "business_analyst"
ID_PRODUCT_OWNER = "product_owner"
ID_TESTER = "tester"
ID_ARCHITECT = "architect"
ID_TECHNICAL_MANAGER = "technical_manager"
ID_SMALL_BUSINESS_OWNER = "small_business_owner"
ID_STUDENT = "student"

DEFAULT_CHAT_PERSONA = ID_WIKI_MAINTAINER
DEFAULT_STUDENT_GRADE = "9"

_PERSONA_IDS = frozenset(
    {
        ID_WIKI_MAINTAINER,
        ID_SOFTWARE_ENGINEER,
        ID_BUSINESS_ANALYST,
        ID_PRODUCT_OWNER,
        ID_TESTER,
        ID_ARCHITECT,
        ID_TECHNICAL_MANAGER,
        ID_SMALL_BUSINESS_OWNER,
        ID_STUDENT,
    }
)

_GRADE_TOKENS: dict[str, str] = {"K": "K", **{str(n): str(n) for n in range(1, 13)}}


@dataclass(frozen=True)
class PersonaMeta:
    id: str
    label: str


@dataclass(frozen=True)
class GradeOption:
    id: str
    label: str


def all_personas() -> list[PersonaMeta]:
    return [
        PersonaMeta(ID_WIKI_MAINTAINER, "Wiki maintainer"),
        PersonaMeta(ID_SOFTWARE_ENGINEER, "Software engineer"),
        PersonaMeta(ID_BUSINESS_ANALYST, "Business analyst"),
        PersonaMeta(ID_PRODUCT_OWNER, "Product owner"),
        PersonaMeta(ID_TESTER, "Tester / QA"),
        PersonaMeta(ID_ARCHITECT, "Architect"),
        PersonaMeta(ID_TECHNICAL_MANAGER, "Technical manager"),
        PersonaMeta(ID_SMALL_BUSINESS_OWNER, "Small business owner"),
        PersonaMeta(ID_STUDENT, "Student"),
    ]


def student_grade_options() -> list[GradeOption]:
    opts = [GradeOption("K", "Kindergarten")]
    opts.extend(GradeOption(str(n), f"Grade {n}") for n in range(1, 13))
    return opts


def normalize_chat_persona(raw: str) -> str:
    token = (raw or "").strip()
    if token in _PERSONA_IDS:
        return token
    return DEFAULT_CHAT_PERSONA


def resolved_student_grade_token(grade: str) -> str:
    g = (grade or "").strip()
    if g.upper() == "K":
        return "K"
    return _GRADE_TOKENS.get(g, DEFAULT_STUDENT_GRADE)


def grade_display_label(grade_token: str) -> str:
    tok = resolved_student_grade_token(grade_token)
    if tok == "K":
        return "Kindergarten"
    return f"Grade {tok}"


def persona_label_for_id(persona_id: str) -> str:
    pid = normalize_chat_persona(persona_id)
    for p in all_personas():
        if p.id == pid:
            return p.label
    return "Wiki maintainer"


def persona_display(*, persona_id: str, student_grade: str | None = None) -> str:
    pid = normalize_chat_persona(persona_id)
    if pid != ID_STUDENT:
        return persona_label_for_id(pid)
    label = grade_display_label(student_grade or DEFAULT_STUDENT_GRADE)
    return f"Student · {label}"


def persona_addon_applied(addon: str | None) -> bool:
    return bool((addon or "").strip())


def _fragment_for_id(persona_id: str, student_grade_token: str | None) -> str:
    fragments = {
        ID_WIKI_MAINTAINER: (
            "You are using the default **wiki maintainer** voice: prioritize accuracy, "
            "vault-appropriate terminology, and alignment with project schema. Keep answers "
            "well-structured for a personal knowledge base."
        ),
        ID_SOFTWARE_ENGINEER: (
            "You are assisting as a **software engineer**: prefer concrete implementation "
            "guidance, debugging steps, tradeoffs, and small verifiable suggestions. When the "
            "evidence is thin, say so; do not invent repo-specific details."
        ),
        ID_BUSINESS_ANALYST: (
            "You are assisting as a **business analyst**: clarify requirements, acceptance "
            "criteria, assumptions, and open questions. Use precise, stakeholder-friendly "
            "language and separate facts (from excerpts) from interpretation."
        ),
        ID_PRODUCT_OWNER: (
            "You are assisting as a **product owner**: emphasize outcomes, user value, "
            "prioritization, risks, and crisp acceptance-style framing. Keep scope explicit "
            "and flag ambiguities."
        ),
        ID_TESTER: (
            "You are assisting as a **tester / QA**: think in terms of scenarios, edge cases, "
            "negative paths, repro steps, and testability. Call out missing information needed "
            "to validate behavior."
        ),
        ID_ARCHITECT: (
            "You are assisting as a **software architect**: emphasize boundaries, interfaces, "
            "non-functional requirements, consistency, and evolution of the system. Prefer "
            "diagrams-in-words when helpful."
        ),
        ID_TECHNICAL_MANAGER: (
            "You are assisting as a **technical manager**: balance delivery, risk, dependencies, "
            "and communication. Summarize decisions, owners, and next steps when appropriate."
        ),
        ID_SMALL_BUSINESS_OWNER: (
            "You are assisting as a **small business owner**: prioritize practical outcomes, "
            "cash flow and customer impact, time constraints, and clear tradeoffs. Favor concise, "
            "actionable guidance; flag when professional legal, tax, or accounting advice is "
            "needed rather than guessing."
        ),
    }
    if persona_id == ID_STUDENT:
        level = grade_display_label(student_grade_token or DEFAULT_STUDENT_GRADE)
        return (
            f"You are assisting a **student** at **{level}**. Use age-appropriate vocabulary and "
            "clear step-by-step explanations. Encourage understanding over jargon; define terms "
            "when needed. Do not assume university or professional workplace context unless the "
            "provided material clearly requires it."
        )
    return fragments.get(persona_id, fragments[ID_WIKI_MAINTAINER])


def persona_prompt_fragment(persona_id: str, student_grade: str | None = None) -> str:
    pid = normalize_chat_persona(persona_id)
    grade = resolved_student_grade_token(student_grade or DEFAULT_STUDENT_GRADE) if pid == ID_STUDENT else None
    return _fragment_for_id(pid, grade)


def build_persona_system_section(
    *,
    persona_id: str,
    student_grade: str | None = None,
    addon: str | None = None,
) -> str:
    base = persona_prompt_fragment(persona_id, student_grade)
    parts = [f"### User persona\n{base}\n"]
    addon_text = (addon or "").strip()
    if addon_text:
        parts.append(f"\n### User-provided persona notes\n{addon_text}\n")
    parts.append("\n")
    return "".join(parts)


def join_nonempty(*blocks: str | None) -> str | None:
    texts = [b.strip() for b in blocks if b and b.strip()]
    if not texts:
        return None
    return "\n\n".join(texts)
