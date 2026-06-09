import { CheckCircle2, ExternalLink, EyeOff, Plus, RotateCcw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { PageNav } from "../components/PageNav";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { api } from "../lib/api";
import { useFiscalYear } from "../lib/fiscalYear";
import { formatCurrency } from "../lib/utils";
import type { JiraProjectCatalog, Product, ProductJiraSpace, ProductJiraSpacePayload } from "../types/api";

type ProductUpdate = Partial<Pick<Product, "name" | "description" | "budget_amount" | "is_active">>;
type ProductSpacesById = Record<number, ProductJiraSpace[]>;
type JiraKeyOwner = { productId: number; productName: string };

export function ProductSettingsPage() {
  const { fiscalYearLabel, fiscalYearRangeLabel, fiscalYear } = useFiscalYear();
  const [products, setProducts] = useState<Product[]>([]);
  const [jiraCatalog, setJiraCatalog] = useState<JiraProjectCatalog[]>([]);
  const [productSpaces, setProductSpaces] = useState<ProductSpacesById>({});
  const [newProduct, setNewProduct] = useState({
    name: "",
    budget: "",
    description: "",
  });
  const [creating, setCreating] = useState(false);
  const [savingIds, setSavingIds] = useState<Set<number>>(new Set());
  const [deletingIds, setDeletingIds] = useState<Set<number>>(new Set());
  const [spaceActionIds, setSpaceActionIds] = useState<Set<string>>(new Set());
  const [catalogActionIds, setCatalogActionIds] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [catalogFilter, setCatalogFilter] = useState("");
  const [unmappedPanelOpen, setUnmappedPanelOpen] = useState(true);

  const loadSettings = useCallback(async () => {
    const [productRows, catalogRows] = await Promise.all([api.products(fiscalYear), api.jiraProjectCatalog()]);
    const spacesEntries = await Promise.all(
      productRows.map(async (product) => [product.id, await api.productJiraSpaces(product.id)] as const),
    );
    setProducts(productRows);
    setJiraCatalog(catalogRows);
    setProductSpaces(Object.fromEntries(spacesEntries) as ProductSpacesById);
  }, [fiscalYear]);

  const mappedJiraKeys = useMemo(() => {
    return new Set(Object.values(productSpaces).flatMap((spaces) => spaces.map((space) => space.jira_project_key)));
  }, [productSpaces]);

  const jiraKeyOwners = useMemo(() => {
    const productNames = new Map(products.map((product) => [product.id, product.name]));
    const owners = new Map<string, JiraKeyOwner>();
    for (const [productId, spaces] of Object.entries(productSpaces)) {
      const numericProductId = Number(productId);
      const productName = productNames.get(numericProductId) ?? "Unknown product";
      for (const space of spaces) {
        owners.set(space.jira_project_key, { productId: numericProductId, productName });
      }
    }
    return owners;
  }, [products, productSpaces]);

  const unmappedCatalogProjects = useMemo(() => {
    return jiraCatalog
      .filter((project) => !mappedJiraKeys.has(project.jira_project_key))
      .sort((left, right) => Number(right.is_visible) - Number(left.is_visible) || left.jira_project_key.localeCompare(right.jira_project_key));
  }, [jiraCatalog, mappedJiraKeys]);

  async function createProduct() {
    const name = newProduct.name.trim();
    if (!name) return;
    const budgetAmount = newProduct.budget.trim() === "" ? 0 : Number(newProduct.budget);
    if (!Number.isFinite(budgetAmount) || budgetAmount < 0) {
      setError("Budget must be zero or greater");
      return;
    }
    setCreating(true);
    setError(null);
    setNotice(null);
    try {
      const created = await api.createProduct(
        {
          name,
          jira_space_key: null,
          budget_amount: budgetAmount,
          description: newProduct.description.trim() || null,
          is_active: true,
        },
        fiscalYear,
      );
      setProducts((current) => [...current, created].sort((left, right) => left.name.localeCompare(right.name)));
      setProductSpaces((current) => ({ ...current, [created.id]: [] }));
      setNewProduct({ name: "", budget: "", description: "" });
      setNotice(`${created.name} was added. Assign Jira projects from the product row when ready.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to add product");
    } finally {
      setCreating(false);
    }
  }

  useEffect(() => {
    loadSettings()
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Unable to load products"))
      .finally(() => setLoading(false));
  }, [loadSettings]);

  const updateProduct = useCallback(async (product: Product, payload: ProductUpdate) => {
    setSavingIds((current) => new Set(current).add(product.id));
    setError(null);
    setNotice(null);
    try {
      const updated = await api.updateProduct(product.id, payload, fiscalYear);
      setProducts((current) => current.map((row) => (row.id === product.id ? updated : row)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update product");
    } finally {
      setSavingIds((current) => {
        const next = new Set(current);
        next.delete(product.id);
        return next;
      });
    }
  }, [fiscalYear]);

  const deleteProduct = useCallback(
    async (product: Product) => {
      const spaces = productSpaces[product.id] ?? [];
      if (spaces.length > 0) {
        setError("Remove mapped Jira projects before deleting this product");
        return;
      }
      if (!window.confirm(`Delete ${product.name}? This will remove the product from SPARC.`)) return;
      setDeletingIds((current) => new Set(current).add(product.id));
      setError(null);
      setNotice(null);
      try {
        await api.deleteProduct(product.id);
        setProducts((current) => current.filter((row) => row.id !== product.id));
        setProductSpaces((current) => {
          const next = { ...current };
          delete next[product.id];
          return next;
        });
        setNotice(`${product.name} was deleted.`);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to delete product");
      } finally {
        setDeletingIds((current) => {
          const next = new Set(current);
          next.delete(product.id);
          return next;
        });
      }
    },
    [productSpaces],
  );

  const addJiraSpace = useCallback(async (product: Product, payload: ProductJiraSpacePayload) => {
    const actionId = `add-${product.id}`;
    setSpaceActionIds((current) => new Set(current).add(actionId));
    setError(null);
    setNotice(null);
    try {
      const created = await api.addProductJiraSpace(product.id, payload);
      setProductSpaces((current) => {
        const next = removeJiraSpaceFromAllProducts(current, created);
        return {
          ...next,
          [product.id]: [...(next[product.id] ?? []), created].sort((left, right) =>
            left.jira_project_key.localeCompare(right.jira_project_key),
          ),
        };
      });
      setNotice(`${created.jira_project_key} was mapped to ${product.name}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to add Jira project");
    } finally {
      setSpaceActionIds((current) => {
        const next = new Set(current);
        next.delete(actionId);
        return next;
      });
    }
  }, []);

  const updateJiraSpace = useCallback(
    async (product: Product, space: ProductJiraSpace, payload: Partial<Pick<ProductJiraSpace, "is_active" | "scope_jql">>) => {
      const actionId = `update-${product.id}-${space.id}`;
      setSpaceActionIds((current) => new Set(current).add(actionId));
      setError(null);
      setNotice(null);
      try {
        const updated = await api.updateProductJiraSpace(product.id, space.id, payload);
        setProductSpaces((current) => ({
          ...current,
          [product.id]: (current[product.id] ?? []).map((row) => (row.id === updated.id ? updated : row)),
        }));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to update Jira project");
      } finally {
        setSpaceActionIds((current) => {
          const next = new Set(current);
          next.delete(actionId);
          return next;
        });
      }
    },
    [],
  );

  const validateJiraSpace = useCallback(async (product: Product, space: ProductJiraSpace) => {
    const actionId = `validate-${product.id}-${space.id}`;
    setSpaceActionIds((current) => new Set(current).add(actionId));
    setError(null);
    setNotice(null);
    try {
      const updated = await api.validateProductJiraSpace(product.id, space.id);
      setProductSpaces((current) => ({
        ...current,
        [product.id]: (current[product.id] ?? []).map((row) => (row.id === updated.id ? updated : row)),
      }));
      setNotice(`${updated.jira_project_key} was validated.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to validate Jira project");
    } finally {
      setSpaceActionIds((current) => {
        const next = new Set(current);
        next.delete(actionId);
        return next;
      });
    }
  }, []);

  const removeJiraSpace = useCallback(async (product: Product, space: ProductJiraSpace) => {
    if (!window.confirm(`Remove ${space.jira_project_key} from ${product.name}?`)) return;
    const actionId = `remove-${product.id}-${space.id}`;
    setSpaceActionIds((current) => new Set(current).add(actionId));
    setError(null);
    setNotice(null);
    try {
      await api.removeProductJiraSpace(product.id, space.id);
      setProductSpaces((current) => ({
        ...current,
        [product.id]: (current[product.id] ?? []).filter((row) => row.id !== space.id),
      }));
      setNotice(`${space.jira_project_key} was removed from ${product.name}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to remove Jira project");
    } finally {
      setSpaceActionIds((current) => {
        const next = new Set(current);
        next.delete(actionId);
        return next;
      });
    }
  }, []);

  const updateCatalogProjectVisibility = useCallback(async (project: JiraProjectCatalog, isVisible: boolean) => {
    setCatalogActionIds((current) => new Set(current).add(project.id));
    setError(null);
    setNotice(null);
    try {
      const updated = await api.updateJiraProjectCatalog(project.id, { is_visible: isVisible });
      setJiraCatalog((current) => current.map((row) => (row.id === updated.id ? updated : row)));
      setNotice(`${updated.jira_project_key} was ${isVisible ? "restored to" : "ignored in"} the unmapped Jira project list.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update Jira project");
    } finally {
      setCatalogActionIds((current) => {
        const next = new Set(current);
        next.delete(project.id);
        return next;
      });
    }
  }, []);

  if (loading) return <LoadingBlock />;
  if (error && products.length === 0) return <ErrorBlock message={error} />;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Product Settings</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Maintain {fiscalYearLabel} budgets ({fiscalYearRangeLabel}) and map each SPARC product to one or more Jira projects.
          </p>
        </div>
        <PageNav current="products" />
      </div>

      {notice ? <div className="rounded-md border border-[color:var(--spark-cyan)] bg-accent/10 px-3 py-2 text-sm text-primary">{notice}</div> : null}
      {error ? <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}

      <section className="rounded-lg border bg-card p-4">
        <div className="mb-3">
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">Add Product</h2>
          <p className="mt-1 text-sm text-muted-foreground">Budget entered here applies to {fiscalYearLabel} only.</p>
        </div>
        <div className="grid gap-3 lg:grid-cols-[1.2fr_0.7fr_1.8fr_auto]">
          <Input
            aria-label="New product name"
            disabled={creating}
            placeholder="Product name"
            value={newProduct.name}
            onChange={(event) => setNewProduct((current) => ({ ...current, name: event.target.value }))}
          />
          <Input
            aria-label="New product budget"
            className="numeric-cell"
            disabled={creating}
            inputMode="decimal"
            placeholder="Budget"
            value={newProduct.budget}
            onChange={(event) => setNewProduct((current) => ({ ...current, budget: event.target.value }))}
          />
          <Input
            aria-label="New product description"
            disabled={creating}
            placeholder="Description"
            value={newProduct.description}
            onChange={(event) => setNewProduct((current) => ({ ...current, description: event.target.value }))}
            onKeyDown={(event) => {
              if (event.key === "Enter") void createProduct();
            }}
          />
          <Button onClick={createProduct} disabled={creating || !newProduct.name.trim()}>
            <Plus className="h-4 w-4" />
            {creating ? "Adding" : "Add"}
          </Button>
        </div>
      </section>

      <UnmappedJiraProjectsPanel
        isOpen={unmappedPanelOpen}
        onToggle={() => setUnmappedPanelOpen((current) => !current)}
        projects={unmappedCatalogProjects}
        searchValue={catalogFilter}
        busyIds={catalogActionIds}
        totalCatalogCount={jiraCatalog.length}
        onSearchChange={setCatalogFilter}
        onVisibilityChange={updateCatalogProjectVisibility}
      />

      <section className="space-y-4">
        {products.map((product) => (
          <ProductSettingsCard
            key={product.id}
            product={product}
            deleting={deletingIds.has(product.id)}
            saving={savingIds.has(product.id)}
            spaces={productSpaces[product.id] ?? []}
            catalog={jiraCatalog}
            jiraKeyOwners={jiraKeyOwners}
            busyIds={spaceActionIds}
            fiscalYearLabel={fiscalYearLabel}
            onUpdateProduct={(payload) => updateProduct(product, payload)}
            onDeleteProduct={() => deleteProduct(product)}
            onAddSpace={(payload) => addJiraSpace(product, payload)}
            onUpdateSpace={(space, payload) => updateJiraSpace(product, space, payload)}
            onValidateSpace={(space) => validateJiraSpace(product, space)}
            onRemoveSpace={(space) => removeJiraSpace(product, space)}
          />
        ))}
      </section>
    </div>
  );
}

function UnmappedJiraProjectsPanel({
  isOpen,
  onToggle,
  projects,
  searchValue,
  busyIds,
  totalCatalogCount,
  onSearchChange,
  onVisibilityChange,
}: {
  isOpen: boolean;
  onToggle: () => void;
  projects: JiraProjectCatalog[];
  searchValue: string;
  busyIds: Set<number>;
  totalCatalogCount: number;
  onSearchChange: (value: string) => void;
  onVisibilityChange: (project: JiraProjectCatalog, isVisible: boolean) => void | Promise<void>;
}) {
  const normalizedSearch = searchValue.trim().toLowerCase();
  const activeProjects = projects.filter((project) => project.is_visible);
  const ignoredProjects = projects.filter((project) => !project.is_visible);
  const orderedProjects = [...activeProjects, ...ignoredProjects];
  const filteredProjects = orderedProjects.filter((project) => {
    if (!normalizedSearch) return true;
    return (
      project.jira_project_key.toLowerCase().includes(normalizedSearch) ||
      project.jira_project_name.toLowerCase().includes(normalizedSearch) ||
      (project.project_type_key ?? "").toLowerCase().includes(normalizedSearch)
    );
  });
  const archivedCount = projects.filter((project) => project.is_archived).length;
  const ignoredCount = ignoredProjects.length;

  return (
    <section className="rounded-lg border bg-card p-4">
      <div className={`flex flex-col justify-between gap-3 lg:flex-row lg:items-start ${isOpen ? "mb-3" : ""}`}>
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold uppercase text-muted-foreground">Unmapped Jira Projects</h2>
            <Badge className={activeProjects.length ? "border-warning/40 text-warning" : "border-primary/40 text-primary"}>
              {activeProjects.length} unmapped
            </Badge>
            {ignoredCount ? <Badge className="border-muted-foreground/30 bg-muted text-muted-foreground">{ignoredCount} ignored</Badge> : null}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Review catalog projects that are not assigned to a SPARC product. Leave projects here when they should stay out of SPARC reporting.
          </p>
        </div>
        <div className="grid gap-2 sm:grid-cols-[9rem_9rem_9rem_auto]">
          <div className="rounded-md bg-secondary/50 px-3 py-2">
            <div className="text-xs font-semibold uppercase text-muted-foreground">Catalog</div>
            <div className="numeric-cell mt-1 text-lg font-semibold text-primary">{totalCatalogCount}</div>
          </div>
          <div className="rounded-md bg-secondary/50 px-3 py-2">
            <div className="text-xs font-semibold uppercase text-muted-foreground">Archived</div>
            <div className="numeric-cell mt-1 text-lg font-semibold text-primary">{archivedCount}</div>
          </div>
          <div className="rounded-md bg-secondary/50 px-3 py-2">
            <div className="text-xs font-semibold uppercase text-muted-foreground">Ignored</div>
            <div className="numeric-cell mt-1 text-lg font-semibold text-primary">{ignoredCount}</div>
          </div>
          <Button type="button" variant="outline" onClick={onToggle}>
            {isOpen ? "Collapse" : "Review Projects"}
          </Button>
        </div>
      </div>

      {isOpen ? (
        <>
          <Input
            aria-label="Search unmapped Jira projects"
            className="mb-3 h-10 max-w-md"
            placeholder="Search Jira projects"
            value={searchValue}
            onChange={(event) => onSearchChange(event.target.value)}
          />

          {projects.length === 0 ? (
            <div className="rounded-md bg-secondary/50 p-4 text-sm text-muted-foreground">Every Jira catalog project is currently assigned.</div>
          ) : (
            <div className="max-h-80 overflow-auto rounded-md border bg-background">
              <div className="grid min-w-[820px] grid-cols-[8rem_minmax(18rem,1fr)_9rem_9rem_7rem] border-b bg-muted/60 px-3 py-2 text-xs font-semibold uppercase text-muted-foreground">
                <div>Key</div>
                <div>Name</div>
                <div>Type</div>
                <div>Last Seen</div>
                <div className="text-right">Action</div>
              </div>
              {filteredProjects.length ? (
                filteredProjects.map((project) => (
                  <div
                    key={project.id}
                    className={`grid min-w-[820px] grid-cols-[8rem_minmax(18rem,1fr)_9rem_9rem_7rem] items-center gap-2 border-b px-3 py-2 text-sm last:border-b-0 ${
                      project.is_visible ? "" : "bg-secondary/40 text-muted-foreground"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className={`font-semibold ${project.is_visible ? "text-primary" : "text-muted-foreground"}`}>
                        {project.jira_project_key}
                      </span>
                      {project.is_archived ? <Badge className="border-muted-foreground/30 bg-muted text-muted-foreground">Archived</Badge> : null}
                      {!project.is_visible ? <Badge className="border-muted-foreground/30 bg-muted text-muted-foreground">Ignored</Badge> : null}
                    </div>
                    <div className="min-w-0 truncate">{project.jira_project_name}</div>
                    <div className="text-muted-foreground">{project.project_type_key ?? "Unknown"}</div>
                    <div className="text-xs text-muted-foreground">{formatDate(project.last_seen_at)}</div>
                    <div className="flex justify-end">
                      <Button
                        type="button"
                        variant={project.is_visible ? "ghost" : "outline"}
                        size="sm"
                        disabled={busyIds.has(project.id)}
                        onClick={() => void onVisibilityChange(project, !project.is_visible)}
                      >
                        {project.is_visible ? <EyeOff className="h-4 w-4" /> : <RotateCcw className="h-4 w-4" />}
                        {busyIds.has(project.id) ? "Saving" : project.is_visible ? "Ignore" : "Restore"}
                      </Button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-4 text-sm text-muted-foreground">No unmapped Jira projects match this search.</div>
              )}
            </div>
          )}
        </>
      ) : (
        <div className="mt-3 text-sm text-muted-foreground">
          Hidden for now. Reopen when you need to review unassigned Jira projects.
        </div>
      )}
    </section>
  );
}

function ProductSettingsCard({
  product,
  deleting,
  saving,
  spaces,
  catalog,
  jiraKeyOwners,
  busyIds,
  fiscalYearLabel,
  onUpdateProduct,
  onDeleteProduct,
  onAddSpace,
  onUpdateSpace,
  onValidateSpace,
  onRemoveSpace,
}: {
  product: Product;
  deleting: boolean;
  saving: boolean;
  spaces: ProductJiraSpace[];
  catalog: JiraProjectCatalog[];
  jiraKeyOwners: Map<string, JiraKeyOwner>;
  busyIds: Set<string>;
  fiscalYearLabel: string;
  onUpdateProduct: (payload: ProductUpdate) => void | Promise<void>;
  onDeleteProduct: () => void | Promise<void>;
  onAddSpace: (payload: ProductJiraSpacePayload) => void | Promise<void>;
  onUpdateSpace: (space: ProductJiraSpace, payload: Partial<Pick<ProductJiraSpace, "is_active" | "scope_jql">>) => void | Promise<void>;
  onValidateSpace: (space: ProductJiraSpace) => void | Promise<void>;
  onRemoveSpace: (space: ProductJiraSpace) => void | Promise<void>;
}) {
  return (
    <article className="rounded-lg border bg-card p-4">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.4fr)]">
        <div className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0 flex-1 space-y-1">
              <TextInput
                ariaLabel={`${product.name} product name`}
                allowEmpty={false}
                className="text-base font-semibold"
                disabled={saving}
                value={product.name}
                onCommit={(name) => onUpdateProduct({ name })}
              />
              <Link className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline" to={`/products/${product.id}`}>
                View product detail
                <ExternalLink className="h-3 w-3" />
              </Link>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <StatusSelect product={product} disabled={saving || deleting} onCommit={(is_active) => onUpdateProduct({ is_active })} />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={saving || deleting || spaces.length > 0}
                title={spaces.length > 0 ? "Remove mapped Jira projects before deleting this product" : `Delete ${product.name}`}
                onClick={() => void onDeleteProduct()}
              >
                <Trash2 className="h-4 w-4" />
                {deleting ? "Deleting" : "Delete"}
              </Button>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-[10rem_1fr]">
            <div>
              <div className="mb-1 text-xs font-semibold uppercase text-muted-foreground">{fiscalYearLabel} Budget</div>
              <BudgetInput product={product} disabled={saving} onCommit={(budget_amount) => onUpdateProduct({ budget_amount })} />
            </div>
            <label className="block space-y-1">
              <span className="text-xs font-semibold uppercase text-muted-foreground">Description</span>
              <TextInput
                ariaLabel={`${product.name} description`}
                disabled={saving}
                placeholder="No description"
                value={product.description ?? ""}
                onCommit={(description) => onUpdateProduct({ description: description || null })}
              />
            </label>
          </div>

          <div className="text-xs text-muted-foreground">Last updated {formatDate(product.updated_at)}</div>
        </div>

        <div className="rounded-md border bg-background/60 p-3">
          <div className="mb-3 flex flex-col justify-between gap-1 sm:flex-row sm:items-center">
            <div>
              <h2 className="text-sm font-semibold uppercase text-muted-foreground">Jira Projects</h2>
              <p className="text-sm text-muted-foreground">One SPARC product can own multiple Jira projects.</p>
            </div>
            <Badge className={spaces.length ? "border-primary/40 text-primary" : "border-muted text-muted-foreground"}>
              {spaces.length} mapped
            </Badge>
          </div>
          <ProductJiraSpacesEditor
            product={product}
            spaces={spaces}
            catalog={catalog}
            jiraKeyOwners={jiraKeyOwners}
            busyIds={busyIds}
            onAdd={onAddSpace}
            onUpdate={onUpdateSpace}
            onValidate={onValidateSpace}
            onRemove={onRemoveSpace}
          />
        </div>
      </div>
    </article>
  );
}

function ProductJiraSpacesEditor({
  product,
  spaces,
  catalog,
  jiraKeyOwners,
  busyIds,
  onAdd,
  onUpdate,
  onValidate,
  onRemove,
}: {
  product: Product;
  spaces: ProductJiraSpace[];
  catalog: JiraProjectCatalog[];
  jiraKeyOwners: Map<string, JiraKeyOwner>;
  busyIds: Set<string>;
  onAdd: (payload: ProductJiraSpacePayload) => void | Promise<void>;
  onUpdate: (space: ProductJiraSpace, payload: Partial<Pick<ProductJiraSpace, "is_active" | "scope_jql">>) => void | Promise<void>;
  onValidate: (space: ProductJiraSpace) => void | Promise<void>;
  onRemove: (space: ProductJiraSpace) => void | Promise<void>;
}) {
  const [selectedCatalogId, setSelectedCatalogId] = useState("");
  const [manualKey, setManualKey] = useState("");
  const addBusy = busyIds.has(`add-${product.id}`);
  const productKeys = useMemo(() => new Set(spaces.map((space) => space.jira_project_key)), [spaces]);
  const availableCatalog = useMemo(
    () =>
      catalog
        .filter((project) => project.is_visible && !productKeys.has(project.jira_project_key) && !jiraKeyOwners.has(project.jira_project_key))
        .sort((left, right) => left.jira_project_key.localeCompare(right.jira_project_key)),
    [catalog, jiraKeyOwners, productKeys],
  );
  const selectedProject = availableCatalog.find((project) => String(project.id) === selectedCatalogId);
  const manualKeyNormalized = manualKey.trim().toUpperCase();
  const manualKeyOwner = manualKeyNormalized ? jiraKeyOwners.get(manualKeyNormalized) : undefined;
  const manualKeyAlreadyMappedHere = manualKeyNormalized ? productKeys.has(manualKeyNormalized) || manualKeyOwner?.productId === product.id : false;
  const manualKeyMappedElsewhere = manualKeyOwner !== undefined && manualKeyOwner.productId !== product.id;

  function addSelectedCatalog() {
    const catalogId = Number(selectedCatalogId);
    if (!Number.isFinite(catalogId) || selectedProject === undefined) return;
    void onAdd({ jira_project_catalog_id: catalogId, is_active: true });
    setSelectedCatalogId("");
  }

  function addManualKey() {
    const key = manualKey.trim().toUpperCase();
    if (!key || manualKeyAlreadyMappedHere || manualKeyMappedElsewhere) return;
    void onAdd({ jira_project_key: key, is_active: true });
    setManualKey("");
  }

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        {spaces.length === 0 ? <div className="text-sm text-muted-foreground">No Jira projects mapped.</div> : null}
        {spaces.map((space) => {
          const updating = busyIds.has(`update-${product.id}-${space.id}`);
          const validating = busyIds.has(`validate-${product.id}-${space.id}`);
          const removing = busyIds.has(`remove-${product.id}-${space.id}`);
          const busy = updating || validating || removing;
          return (
            <div key={space.id} className="rounded-md border bg-background p-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-primary">{space.jira_project_key}</span>
                    <span className="max-w-72 truncate text-sm text-muted-foreground">{space.jira_project_name ?? "Unknown Jira project"}</span>
                    <ValidationBadge status={space.validation_status} />
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">{space.validation_message ?? "Not validated yet"}</div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <select
                    aria-label={`${space.jira_project_key} mapping status`}
                    className="h-8 rounded-md border border-input bg-background px-2 text-sm"
                    disabled={busy}
                    value={space.is_active ? "active" : "inactive"}
                    onChange={(event) => void onUpdate(space, { is_active: event.target.value === "active" })}
                  >
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                  </select>
                  <Button type="button" variant="outline" size="sm" disabled={busy} onClick={() => void onValidate(space)}>
                    <CheckCircle2 className="h-4 w-4" />
                    {validating ? "Checking" : "Validate"}
                  </Button>
                  <Button type="button" variant="ghost" size="sm" disabled={busy} onClick={() => void onRemove(space)}>
                    <Trash2 className="h-4 w-4" />
                    Remove
                  </Button>
                </div>
              </div>
              <div className="mt-2">
                <TextInput
                  ariaLabel={`${space.jira_project_key} scope JQL`}
                  className="h-8"
                  disabled={busy}
                  placeholder="Optional scope JQL"
                  value={space.scope_jql ?? ""}
                  onCommit={(scope_jql) => onUpdate(space, { scope_jql: scope_jql || null })}
                />
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid gap-2 lg:grid-cols-[1fr_auto_0.7fr_auto]">
        <select
          aria-label={`${product.name} Jira project catalog`}
          className="h-9 min-w-0 rounded-md border border-input bg-background px-2 text-sm"
          disabled={addBusy || availableCatalog.length === 0}
          value={selectedCatalogId}
          onChange={(event) => setSelectedCatalogId(event.target.value)}
        >
          <option value="">{availableCatalog.length === 0 ? "No catalog projects available" : "Select Jira project"}</option>
          {availableCatalog.map((project) => (
            <option key={project.id} value={project.id}>
              {project.jira_project_key} - {project.jira_project_name}
            </option>
          ))}
        </select>
        <Button type="button" variant="outline" size="sm" disabled={addBusy || selectedProject === undefined} onClick={addSelectedCatalog}>
          <Plus className="h-4 w-4" />
          Add
        </Button>
        <Input
          aria-label={`${product.name} manual Jira key`}
          className="h-9 uppercase"
          disabled={addBusy}
          placeholder="Manual key"
          value={manualKey}
          onChange={(event) => setManualKey(event.target.value.toUpperCase())}
          onKeyDown={(event) => {
            if (event.key === "Enter") addManualKey();
          }}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={addBusy || !manualKey.trim() || manualKeyAlreadyMappedHere || manualKeyMappedElsewhere}
          onClick={addManualKey}
        >
          <Plus className="h-4 w-4" />
          Add Key
        </Button>
      </div>
      {manualKeyMappedElsewhere ? (
        <div className="text-xs text-muted-foreground">
          {manualKeyNormalized} is already mapped to {manualKeyOwner.productName}.
        </div>
      ) : null}
      {manualKeyAlreadyMappedHere ? <div className="text-xs text-muted-foreground">{manualKeyNormalized} is already mapped to {product.name}.</div> : null}
    </div>
  );
}

function removeJiraSpaceFromAllProducts(current: ProductSpacesById, created: ProductJiraSpace): ProductSpacesById {
  return Object.fromEntries(
    Object.entries(current).map(([productId, spaces]) => [
      Number(productId),
      spaces.filter((space) => space.id !== created.id && space.jira_project_key !== created.jira_project_key),
    ]),
  );
}

function ValidationBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  if (normalized === "valid") {
    return <Badge className="border-[color:var(--spark-cyan)] bg-accent/10 text-primary">Valid</Badge>;
  }
  if (normalized === "invalid") {
    return <Badge className="border-destructive/40 bg-destructive/10 text-destructive">Invalid</Badge>;
  }
  return <Badge className="border-muted-foreground/30 bg-muted text-muted-foreground">Unknown</Badge>;
}

function TextInput({
  allowEmpty = true,
  ariaLabel,
  className,
  disabled,
  formatter = (value) => value.trim(),
  placeholder,
  value,
  onCommit,
}: {
  allowEmpty?: boolean;
  ariaLabel: string;
  className?: string;
  disabled?: boolean;
  formatter?: (value: string) => string;
  placeholder?: string;
  value: string;
  onCommit: (value: string) => void | Promise<void>;
}) {
  const [draft, setDraft] = useState(value);

  useEffect(() => setDraft(value), [value]);

  function commit() {
    const nextValue = formatter(draft);
    if (!allowEmpty && nextValue === "") {
      setDraft(value);
      return;
    }
    setDraft(nextValue);
    if (nextValue === value) return;
    void onCommit(nextValue);
  }

  return (
    <Input
      aria-label={ariaLabel}
      className={className}
      disabled={disabled}
      placeholder={placeholder}
      value={draft}
      onBlur={commit}
      onChange={(event) => setDraft(event.target.value)}
      onKeyDown={(event) => {
        if (event.key === "Enter") event.currentTarget.blur();
      }}
    />
  );
}

function BudgetInput({
  product,
  disabled,
  onCommit,
}: {
  product: Product;
  disabled?: boolean;
  onCommit: (budgetAmount: number) => void | Promise<void>;
}) {
  const [value, setValue] = useState(product.budget_amount > 0 ? String(product.budget_amount) : "");

  useEffect(() => setValue(product.budget_amount > 0 ? String(product.budget_amount) : ""), [product.budget_amount]);

  function commit() {
    const nextValue = value.trim() === "" ? 0 : Number(value);
    if (!Number.isFinite(nextValue) || nextValue < 0 || nextValue === product.budget_amount) return;
    void onCommit(nextValue);
  }

  const invalid = value !== "" && (!Number.isFinite(Number(value)) || Number(value) < 0);

  return (
    <div className="w-36">
      <Input
        aria-label={`${product.name} budget`}
        className={`numeric-cell h-8 ${invalid ? "border-destructive" : ""}`}
        disabled={disabled}
        inputMode="decimal"
        pattern="[0-9]*"
        placeholder="Not set"
        type="text"
        value={value}
        onBlur={commit}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur();
        }}
      />
      <div className="numeric-cell mt-1 text-xs text-muted-foreground">{formatCurrency(product.budget_amount)}</div>
    </div>
  );
}

function StatusSelect({
  product,
  disabled,
  onCommit,
}: {
  product: Product;
  disabled?: boolean;
  onCommit: (isActive: boolean) => void | Promise<void>;
}) {
  return (
    <select
      aria-label={`${product.name} status`}
      className="h-8 rounded-md border border-input bg-background px-2 text-sm"
      disabled={disabled}
      value={product.is_active ? "active" : "inactive"}
      onChange={(event) => void onCommit(event.target.value === "active")}
    >
      <option value="active">Active</option>
      <option value="inactive">Inactive</option>
    </select>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}
