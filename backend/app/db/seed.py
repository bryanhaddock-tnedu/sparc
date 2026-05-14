from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActualEntry, Bucket, ForecastEntry, JiraProductMapping, JiraUserMapping, Product, TeamMember
from app.services.fiscal_year import ensure_fiscal_months
from app.services.forecasting import upsert_forecast_entry
from app.services.jira_rovo import run_mock_jira_rovo_sync

BUCKETS = [
    ("NET_NEW", "Net New"),
    ("ENHANCE", "Enhance"),
    ("MAINTENANCE", "Maintenance"),
]

PRODUCTS = [
    {
        "name": "Student Information",
        "jira_space_key": "SIS",
        "description": "Core student records, enrollment, and reporting workflows.",
        "budget_amount": Decimal("72000.00"),
    },
    {
        "name": "Educator Licensing",
        "jira_space_key": "EDL",
        "description": "Licensing workflows, renewals, and educator credential services.",
        "budget_amount": Decimal("58000.00"),
    },
    {
        "name": "Data Warehouse",
        "jira_space_key": "DWH",
        "description": "Analytics data platform, extracts, and cross-program reporting.",
        "budget_amount": Decimal("84000.00"),
    },
]

TEAM_MEMBERS = [
    {
        "staff_id": "SPARK-001",
        "name": "Avery Johnson",
        "role": "Product Engineer",
        "team": "Applications",
        "bill_rate": Decimal("115.00"),
        "employment_type": "Employee",
    },
    {
        "staff_id": "SPARK-002",
        "name": "Morgan Lee",
        "role": "Business Analyst",
        "team": "Product",
        "bill_rate": Decimal("95.00"),
        "employment_type": "Employee",
    },
    {
        "staff_id": "SPARK-003",
        "name": "Sam Patel",
        "role": "Systems Analyst",
        "team": "Operations",
        "bill_rate": Decimal("105.00"),
        "employment_type": "Contractor",
        "contracting_company": "Northstar Tech",
    },
    {
        "staff_id": "SPARK-004",
        "name": "Riley Chen",
        "role": "Data Engineer",
        "team": "Data Services",
        "bill_rate": Decimal("125.00"),
        "employment_type": "Employee",
    },
    {
        "staff_id": "SPARK-005",
        "name": "Jordan Smith",
        "role": "QA Analyst",
        "team": "Quality",
        "bill_rate": Decimal("88.00"),
        "employment_type": "Contractor",
        "contracting_company": "ClearPath Consulting",
    },
]

JIRA_USER_LINKS = {
    "acct-avery": "Avery Johnson",
    "acct-morgan": "Morgan Lee",
    "acct-sam": "Sam Patel",
    "acct-riley": "Riley Chen",
    "acct-jordan": "Jordan Smith",
}

JIRA_PRODUCT_LINKS = {
    "SIS": "Student Information",
    "EDL": "Educator Licensing",
    "DWH": "Data Warehouse",
}


def seed_database(db: Session) -> None:
    _seed_buckets(db)
    ensure_fiscal_months(db, 2026)
    products = _seed_products(db)
    members = _seed_team_members(db)
    _seed_jira_mappings(db, products, members)
    _seed_forecasts(db, products, members)
    if db.scalar(select(ActualEntry.id).limit(1)) is None:
        run_mock_jira_rovo_sync(db)
    db.commit()


def _seed_buckets(db: Session) -> None:
    for code, name in BUCKETS:
        existing = db.scalar(select(Bucket).where(Bucket.code == code))
        if existing is None:
            db.add(Bucket(code=code, name=name))
    db.flush()


def _seed_products(db: Session) -> dict[str, Product]:
    products: dict[str, Product] = {}
    for payload in PRODUCTS:
        product = db.scalar(select(Product).where(Product.name == payload["name"]))
        if product is None:
            product = Product(**payload)
            db.add(product)
            db.flush()
        elif not product.budget_amount:
            product.budget_amount = payload["budget_amount"]
        products[product.name] = product
    return products


def _seed_team_members(db: Session) -> dict[str, TeamMember]:
    members: dict[str, TeamMember] = {}
    for payload in TEAM_MEMBERS:
        member = db.scalar(select(TeamMember).where(TeamMember.staff_id == payload["staff_id"]))
        if member is None:
            member = TeamMember(**payload)
            db.add(member)
            db.flush()
        members[member.name] = member
    return members


def _seed_jira_mappings(db: Session, products: dict[str, Product], members: dict[str, TeamMember]) -> None:
    for account_id, member_name in JIRA_USER_LINKS.items():
        mapping = db.scalar(select(JiraUserMapping).where(JiraUserMapping.jira_account_id == account_id))
        if mapping is None:
            mapping = JiraUserMapping(
                jira_account_id=account_id,
                jira_display_name=member_name,
                jira_email=f"{member_name.split()[0].lower()}@example.test",
                team_member_id=members[member_name].id,
            )
            db.add(mapping)
        elif mapping.team_member_id is None:
            mapping.team_member_id = members[member_name].id

    for jira_key, product_name in JIRA_PRODUCT_LINKS.items():
        mapping = db.scalar(select(JiraProductMapping).where(JiraProductMapping.jira_project_key == jira_key))
        if mapping is None:
            mapping = JiraProductMapping(
                jira_project_key=jira_key,
                jira_project_name=product_name,
                product_id=products[product_name].id,
            )
            db.add(mapping)
        elif mapping.product_id is None:
            mapping.product_id = products[product_name].id
    db.flush()


def _seed_forecasts(db: Session, products: dict[str, Product], members: dict[str, TeamMember]) -> None:
    if db.scalar(select(ForecastEntry.id).limit(1)) is not None:
        return

    plan = [
        ("Student Information", "Avery Johnson", "NET_NEW", [40, 32, 24, 36, 28, 20, 18, 24, 20, 16, 12, 12]),
        ("Student Information", "Morgan Lee", "ENHANCE", [18, 22, 24, 18, 16, 18, 20, 22, 24, 20, 18, 16]),
        ("Student Information", "Sam Patel", "MAINTENANCE", [14, 12, 16, 14, 12, 12, 10, 12, 14, 16, 12, 10]),
        ("Educator Licensing", "Morgan Lee", "NET_NEW", [20, 18, 22, 24, 26, 22, 18, 16, 18, 20, 22, 24]),
        ("Educator Licensing", "Sam Patel", "MAINTENANCE", [24, 26, 28, 22, 20, 18, 20, 22, 24, 26, 28, 30]),
        ("Educator Licensing", "Jordan Smith", "ENHANCE", [12, 14, 16, 18, 20, 18, 16, 14, 12, 14, 16, 18]),
        ("Data Warehouse", "Riley Chen", "NET_NEW", [34, 36, 38, 42, 40, 36, 32, 30, 28, 26, 24, 22]),
        ("Data Warehouse", "Jordan Smith", "ENHANCE", [16, 18, 20, 22, 24, 22, 20, 18, 16, 18, 20, 22]),
        ("Data Warehouse", "Avery Johnson", "MAINTENANCE", [10, 10, 12, 12, 14, 14, 12, 12, 10, 10, 8, 8]),
    ]

    for product_name, member_name, bucket_code, monthly_hours in plan:
        for sequence, hours in enumerate(monthly_hours, start=1):
            upsert_forecast_entry(
                db,
                product_id=products[product_name].id,
                team_member_id=members[member_name].id,
                bucket_code=bucket_code,
                fiscal_year=2026,
                month_sequence=sequence,
                hours=hours,
            )
