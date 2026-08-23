from __future__ import annotations

from .service_taxonomy import service_slug_from_value


SCOPE_SCHEMA_VERSION = 1
SCOPE_FIELD_PREFIX = "scope_"


def _question(key: str, label: str, options: tuple[tuple[str, str], ...], help_text: str = "") -> dict:
    return {
        "key": key,
        "field_name": f"{SCOPE_FIELD_PREFIX}{key}",
        "label": label,
        "help": help_text,
        "options": tuple({"value": value, "label": option_label} for value, option_label in options),
    }


SPACE_SIZE_OPTIONS = (
    ("studio_1", "Studio or 1 room"),
    ("2_3", "2-3 rooms"),
    ("4_6", "4-6 rooms"),
    ("7_plus", "7+ rooms or a small workplace"),
)
ACCESS_OPTIONS = (
    ("ground", "Ground-level access"),
    ("stairs", "Stairs"),
    ("elevator", "Elevator"),
    ("mixed", "A mix or not sure"),
)
AREA_SIZE_OPTIONS = (
    ("small", "Small area"),
    ("medium", "Medium area"),
    ("large", "Large area"),
    ("unsure", "Not sure yet"),
)


SERVICE_SCOPE_QUESTIONS = {
    "house-cleaning": (
        _question("space_size", "How much space needs cleaning?", SPACE_SIZE_OPTIONS),
        _question(
            "condition",
            "What is the current condition?",
            (("routine", "Routine upkeep"), ("buildup", "Noticeable buildup"), ("heavy", "Heavy buildup"), ("unsure", "Not sure")),
        ),
        _question(
            "supplies",
            "Who should bring supplies?",
            (("contractor", "Contractor"), ("consumer", "I will provide them"), ("discuss", "Discuss after matching")),
        ),
        _question("access", "What access should the contractor expect?", ACCESS_OPTIONS),
    ),
    "deep-cleaning": (
        _question("space_size", "How much space needs cleaning?", SPACE_SIZE_OPTIONS),
        _question(
            "condition",
            "Where is the most buildup?",
            (("kitchen_bath", "Kitchen or bathrooms"), ("throughout", "Throughout the space"), ("floors_windows", "Floors or interior windows"), ("unsure", "Not sure")),
        ),
        _question(
            "occupancy",
            "Will the space be occupied?",
            (("occupied", "Yes"), ("empty", "No, it will be empty"), ("partial", "Partly occupied")),
        ),
        _question("access", "What access should the contractor expect?", ACCESS_OPTIONS),
    ),
    "move-cleaning": (
        _question("space_size", "How much space needs cleaning?", SPACE_SIZE_OPTIONS),
        _question(
            "occupancy",
            "What will be in the space?",
            (("empty", "Empty"), ("some_items", "A few items"), ("furnished", "Mostly furnished")),
        ),
        _question(
            "appliances",
            "Include appliance interiors?",
            (("yes", "Yes"), ("no", "No"), ("discuss", "Discuss after matching")),
        ),
        _question("access", "What access should the contractor expect?", ACCESS_OPTIONS),
    ),
    "packing-unpacking": (
        _question("space_size", "How many rooms are involved?", SPACE_SIZE_OPTIONS),
        _question(
            "materials",
            "Are boxes and packing materials ready?",
            (("ready", "Yes"), ("contractor", "Contractor should provide them"), ("mixed", "Some are ready")),
        ),
        _question("access", "What access should the crew expect?", ACCESS_OPTIONS),
        _question(
            "special_items",
            "Any fragile or oversized items?",
            (("none", "None"), ("fragile", "Fragile items"), ("oversized", "Oversized items"), ("both", "Both")),
        ),
    ),
    "heavy-lifting": (
        _question(
            "item_count",
            "How many heavy items?",
            (("1_2", "1-2"), ("3_5", "3-5"), ("6_plus", "6+"), ("unsure", "Not sure")),
        ),
        _question(
            "heaviest_item",
            "How heavy is the largest item?",
            (("under_100", "Under 100 lb"), ("100_250", "100-250 lb"), ("over_250", "Over 250 lb"), ("unsure", "Not sure")),
        ),
        _question("access", "What access should the crew expect?", ACCESS_OPTIONS),
        _question(
            "transport",
            "Will items leave the property?",
            (("same_property", "No, move within the property"), ("offsite", "Yes, transport is needed")),
            "Off-site transport is a separate service and is not part of the first heavy-lifting lane.",
        ),
    ),
    "furniture-assembly": (
        _question(
            "item_count",
            "How many items need assembly?",
            (("1", "1"), ("2_3", "2-3"), ("4_6", "4-6"), ("7_plus", "7+")),
        ),
        _question(
            "instructions",
            "Are instructions or product links available?",
            (("yes", "Yes"), ("some", "For some items"), ("no", "No")),
        ),
        _question(
            "item_state",
            "What condition are the items in?",
            (("boxed", "Boxed and unopened"), ("opened", "Opened but unassembled"), ("partial", "Partly assembled"), ("mixed", "A mix")),
        ),
        _question(
            "wall_attachment",
            "Does anything need wall or ceiling attachment?",
            (("no", "No"), ("yes", "Yes"), ("unsure", "Not sure")),
            "Attachment work is reviewed separately and is not part of the first assembly lane.",
        ),
    ),
    "lawn-mowing": (
        _question("area_size", "How large is the lawn?", AREA_SIZE_OPTIONS),
        _question(
            "grass_height",
            "How tall is the grass now?",
            (("under_6", "Under 6 inches"), ("6_12", "6-12 inches"), ("over_12", "Over 12 inches"), ("unsure", "Not sure")),
        ),
        _question(
            "terrain",
            "What is the terrain like?",
            (("flat", "Mostly flat"), ("sloped", "Sloped"), ("obstacles", "Trees or obstacles"), ("mixed", "A mix")),
        ),
        _question(
            "recurrence",
            "Is this one-time or recurring?",
            (("one_time", "One-time"), ("recurring", "Recurring"), ("unsure", "Not sure")),
        ),
    ),
    "gardening-planting": (
        _question("area_size", "How large is the garden area?", AREA_SIZE_OPTIONS),
        _question(
            "work_type",
            "What is the main task?",
            (("planting", "Planting"), ("weeding", "Weeding"), ("bed_prep", "Bed preparation"), ("mixed", "A mix")),
        ),
        _question(
            "materials",
            "Who should supply plants or materials?",
            (("consumer", "I will"), ("contractor", "Contractor"), ("discuss", "Discuss after matching")),
        ),
        _question(
            "debris",
            "Should yard debris be removed?",
            (("none", "No debris"), ("bag_only", "Bag or stage it"), ("haul", "Haul-away requested"), ("unsure", "Not sure")),
        ),
    ),
    "landscaping": (
        _question(
            "work_phase",
            "What phase is the project in?",
            (("ideas", "Early ideas"), ("design", "Design needed"), ("install", "Ready to install"), ("maintenance", "Ongoing maintenance")),
        ),
        _question("area_size", "How large is the area?", AREA_SIZE_OPTIONS),
        _question(
            "utilities_changes",
            "Could irrigation, drainage, or electrical work change?",
            (("no", "No"), ("yes", "Yes"), ("unsure", "Not sure")),
        ),
        _question(
            "plan_status",
            "Are plans or measurements available?",
            (("ready", "Yes"), ("partial", "Some"), ("none", "No")),
        ),
    ),
    "local-moving": (
        _question("space_size", "How large is the move?", SPACE_SIZE_OPTIONS),
        _question("origin_access", "Pickup access", ACCESS_OPTIONS),
        _question("destination_access", "Drop-off access", ACCESS_OPTIONS),
        _question(
            "vehicle",
            "What vehicle is likely needed?",
            (("van", "Cargo van"), ("small_truck", "Small box truck"), ("large_truck", "Large truck"), ("unsure", "Not sure")),
        ),
    ),
    "pressure-washing": (
        _question(
            "surface",
            "What is the main surface?",
            (("concrete", "Concrete or masonry"), ("siding", "Siding"), ("deck_fence", "Deck or fence"), ("mixed", "A mix")),
        ),
        _question("area_size", "How large is the area?", AREA_SIZE_OPTIONS),
        _question(
            "water_access",
            "Is an outdoor water connection available?",
            (("yes", "Yes"), ("no", "No"), ("unsure", "Not sure")),
        ),
        _question(
            "height",
            "What height is involved?",
            (("ground", "Ground level"), ("one_story", "One story"), ("two_plus", "Two stories or higher"), ("unsure", "Not sure")),
        ),
    ),
    "window-cleaning": (
        _question(
            "window_count",
            "About how many windows?",
            (("1_10", "1-10"), ("11_20", "11-20"), ("21_40", "21-40"), ("40_plus", "40+")),
        ),
        _question(
            "height",
            "What height is involved?",
            (("ground", "Ground level"), ("one_story", "One story"), ("two_plus", "Two stories or higher"), ("mixed", "A mix")),
        ),
        _question(
            "sides",
            "Which sides should be cleaned?",
            (("interior", "Interior"), ("exterior", "Exterior"), ("both", "Both")),
        ),
        _question("access", "What access should the contractor expect?", ACCESS_OPTIONS),
    ),
    "interior-painting": (
        _question("space_size", "How many rooms or areas?", SPACE_SIZE_OPTIONS),
        _question(
            "wall_condition",
            "What condition are the surfaces in?",
            (("ready", "Ready to paint"), ("minor_repairs", "Minor patching"), ("major_repairs", "Larger repairs"), ("unsure", "Not sure")),
        ),
        _question(
            "occupancy",
            "Will the space be occupied?",
            (("occupied", "Yes"), ("empty", "No"), ("partial", "Partly")),
        ),
        _question(
            "property_age",
            "Was the property likely built before 1978?",
            (("no", "No"), ("yes", "Yes"), ("unsure", "Not sure")),
            "Paint-disturbing work in older properties can require lead-safe practices.",
        ),
    ),
    "kitchen-remodel": (
        _question(
            "work_phase",
            "What phase is the project in?",
            (("ideas", "Early ideas"), ("design", "Design needed"), ("estimates", "Ready for estimates"), ("ready", "Plans are ready")),
        ),
        _question(
            "scope_level",
            "How much is changing?",
            (("finish", "Paint or finish updates"), ("fixtures", "Cabinets, counters, or fixtures"), ("layout", "Layout changes"), ("full", "Full renovation")),
        ),
        _question(
            "utility_relocation",
            "Will plumbing, gas, or electrical locations change?",
            (("no", "No"), ("yes", "Yes"), ("unsure", "Not sure")),
        ),
        _question(
            "plan_status",
            "Are plans or measurements available?",
            (("ready", "Yes"), ("partial", "Some"), ("none", "No")),
        ),
    ),
}


def questions_for_service(service_slug: str | None) -> tuple[dict, ...]:
    return SERVICE_SCOPE_QUESTIONS.get(service_slug_from_value(service_slug), ())


def scope_answer_field_names() -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                question["field_name"]
                for questions in SERVICE_SCOPE_QUESTIONS.values()
                for question in questions
            }
        )
    )


def compact_spaces(value) -> str:
    return " ".join(str(value or "").split())


def clean_scope_answers(service_slug: str | None, payload) -> dict[str, str]:
    answers = {}
    for question in questions_for_service(service_slug):
        answer = compact_spaces(payload.get(question["field_name"])).lower()
        if answer:
            answers[question["key"]] = answer
    return answers


def validate_scope_answers(service_slug: str | None, answers: dict[str, str]) -> list[str]:
    errors = []
    for question in questions_for_service(service_slug):
        answer = answers.get(question["key"], "")
        if not answer:
            continue
        allowed = {option["value"] for option in question["options"]}
        if answer not in allowed:
            errors.append(f"Choose a listed answer for {question['label'].lower()}")
    return errors


def scope_readiness(service_slug: str | None, answers: dict[str, str] | None) -> dict:
    questions = questions_for_service(service_slug)
    answers = answers or {}
    complete = sum(1 for question in questions if answers.get(question["key"]))
    total = len(questions)
    return {
        "complete": complete,
        "total": total,
        "percent": round(complete / total * 100) if total else 0,
        "label": f"{complete} of {total} details ready" if total else "Description only",
    }


def scope_answer_projection(service_slug: str | None, answers_or_rows) -> list[dict]:
    if isinstance(answers_or_rows, dict):
        answers = answers_or_rows
    else:
        answers = {
            str(row["question_key"] if isinstance(row, dict) else row.question_key): str(
                row["answer_code"] if isinstance(row, dict) else row.answer_code
            )
            for row in (answers_or_rows or [])
        }
    rows = []
    for question in questions_for_service(service_slug):
        answer = answers.get(question["key"], "")
        if not answer:
            continue
        option = next(
            (item for item in question["options"] if item["value"] == answer),
            None,
        )
        if option:
            rows.append(
                {
                    "question_key": question["key"],
                    "question_label": question["label"],
                    "answer_code": answer,
                    "answer_label": option["label"],
                    "schema_version": SCOPE_SCHEMA_VERSION,
                }
            )
    return rows
