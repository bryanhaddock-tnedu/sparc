PRODUCT_OFFICES = ("Academics", "Operations", "Programs")

PRODUCT_DIVISIONS_BY_OFFICE: dict[str, tuple[str, ...]] = {
    "Academics": (
        "Academics & Instruction",
        "Post-secondary, Workforce, CTE, & Military Readiness",
        "Centers of Regional Excellence (CORE)",
        "Early Learning",
        "Human Capital",
        "Special Education & Student Supports",
    ),
    "Operations": (
        "Finance",
        "IT",
        "Coordinated School Health",
    ),
    "Programs": (
        "Assessment, Accountability & Research",
        "School Choice",
        "Federal Programs & Oversight",
        "School Turnaround",
        "State Special Schools",
    ),
}

PRODUCT_DIVISIONS = frozenset(
    division
    for divisions in PRODUCT_DIVISIONS_BY_OFFICE.values()
    for division in divisions
)


def clean_product_org_value(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def product_office_error(office: str | None) -> str | None:
    if office is None:
        return None
    if office not in PRODUCT_OFFICES:
        return f"Office must be one of: {', '.join(PRODUCT_OFFICES)}"
    return None


def product_division_error(division: str | None) -> str | None:
    if division is None:
        return None
    if division not in PRODUCT_DIVISIONS:
        return "Division must be one of the configured product divisions"
    return None


def product_org_pair_error(office: str | None, division: str | None) -> str | None:
    office = clean_product_org_value(office)
    division = clean_product_org_value(division)
    if error := product_office_error(office):
        return error
    if error := product_division_error(division):
        return error
    if division is not None and office is None:
        return "Office is required when Division is set"
    if office is not None and division is not None and division not in PRODUCT_DIVISIONS_BY_OFFICE.get(office, ()):
        return f"Division is not available for {office}"
    return None
