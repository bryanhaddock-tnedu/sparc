type ProductRouteTarget = {
  id?: number;
  slug?: string | null;
  product_id?: number;
  product_slug?: string | null;
};

export function productDetailPath(product: ProductRouteTarget): string {
  const slug = "slug" in product ? product.slug : product.product_slug;
  const id = "id" in product ? product.id : product.product_id;
  return `/products/${encodeURIComponent(slug || String(id))}`;
}
