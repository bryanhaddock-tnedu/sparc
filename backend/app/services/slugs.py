import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product, TeamMember


def slugify(value: str | None, fallback: str = "item") -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug or fallback


def product_url_slug(product: Product) -> str:
    return product.slug or slugify(product.name, fallback=f"product-{product.id}")


def unique_product_slug(db: Session, name: str, product_id: int | None = None) -> str:
    base_slug = slugify(name, fallback="product")
    existing = {
        row.slug
        for row in db.scalars(select(Product).where(Product.slug.is_not(None))).all()
        if row.slug and (product_id is None or row.id != product_id)
    }
    slug = base_slug
    suffix = 2
    while slug in existing:
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    return slug


def resolve_product_ref(db: Session, product_ref: str | int) -> Product | None:
    text_ref = str(product_ref).strip()
    if text_ref.isdigit():
        product = db.get(Product, int(text_ref))
        if product is not None:
            return product
    return db.scalar(select(Product).where(Product.slug == text_ref))


def team_member_url_slug(member: TeamMember) -> str:
    return member.slug or slugify(member.name, fallback=f"team-member-{member.id}")


def unique_team_member_slug(db: Session, name: str, team_member_id: int | None = None) -> str:
    base_slug = slugify(name, fallback="team-member")
    existing = {
        row.slug
        for row in db.scalars(select(TeamMember).where(TeamMember.slug.is_not(None))).all()
        if row.slug and (team_member_id is None or row.id != team_member_id)
    }
    slug = base_slug
    suffix = 2
    while slug in existing:
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    return slug


def resolve_team_member_ref(db: Session, team_member_ref: str | int) -> TeamMember | None:
    text_ref = str(team_member_ref).strip()
    if text_ref.isdigit():
        member = db.get(TeamMember, int(text_ref))
        if member is not None:
            return member
    return db.scalar(select(TeamMember).where(TeamMember.slug == text_ref))
