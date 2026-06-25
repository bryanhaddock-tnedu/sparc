type ProductRouteTarget = {
  id?: number;
  slug?: string | null;
  product_id?: number;
  product_slug?: string | null;
};

type TeamMemberRouteTarget = {
  id?: number;
  slug?: string | null;
  memberId?: number;
  memberSlug?: string | null;
  team_member_id?: number;
  team_member_slug?: string | null;
};

export function productDetailPath(product: ProductRouteTarget): string {
  const slug = "slug" in product ? product.slug : product.product_slug;
  const id = "id" in product ? product.id : product.product_id;
  return `/products/${encodeURIComponent(slug || String(id))}`;
}

export function teamMemberDetailPath(member: TeamMemberRouteTarget): string {
  const slug = "slug" in member ? member.slug : "memberSlug" in member ? member.memberSlug : member.team_member_slug;
  const id = "id" in member ? member.id : "memberId" in member ? member.memberId : member.team_member_id;
  return `/team-members/${encodeURIComponent(slug || String(id))}`;
}
