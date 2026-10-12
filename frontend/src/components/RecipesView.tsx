import { useState, useEffect } from "react";
import { useRecipes, useCreateRecipe, useDeleteRecipe, useSettings } from "../hooks";
import type { RecipeIngredient } from "../types";
import ItemSearchInput from "./ItemSearchInput";
import ItemTooltip from "./ItemTooltip";
import { formatGP } from "../lib/format";
import { useToast } from "../context/ToastContext";
import recipeDbJson from "../recipes.json";

const RECIPE_DB = recipeDbJson as Record<string, { id: string; qty: string }[]>;

export default function RecipesView() {
  const { data: recipes, isLoading } = useRecipes();
  const { data: settings } = useSettings();
  const createMutation = useCreateRecipe();
  const deleteMutation = useDeleteRecipe();
  const { toast } = useToast();

  const tooltipsEnabled = (settings?.show_item_tooltips ?? "true") !== "false";

  const [name, setName] = useState("");
  const [outId, setOutId] = useState("");
  const [outQty, setOutQty] = useState("1");
  const [ings, setIngs] = useState<{ id: string; qty: string }[]>([{ id: "", qty: "1" }]);

  useEffect(() => {
    if (outId && RECIPE_DB[outId]) {
      const dbIngs = RECIPE_DB[outId];
      if (Array.isArray(dbIngs) && dbIngs.length > 0) {
        setIngs(dbIngs.map((i) => ({ id: String(i.id), qty: String(i.qty || 1) })));
        toast.info("Auto-populated recipe ingredients!");
      }
    }
  }, [outId]);

  if (isLoading) return <div className="card"><p className="muted">Loading recipes…</p></div>;
  if (!recipes) return null;

  const handleAddRecipe = (e: React.FormEvent) => {
    e.preventDefault();

    if (!name.trim()) {
      toast.error("Please enter a Recipe Name.");
      return;
    }

    if (!outId) {
      toast.error("Please search and select an Output Item.");
      return;
    }

    const parsedOutId = parseInt(outId, 10);
    if (isNaN(parsedOutId)) {
      toast.error("Please select the Output Item from the dropdown.");
      return;
    }

    const parsedIngs = ings
      .filter((i) => i.id && i.qty)
      .map((i) => ({ item_id: parseInt(i.id, 10), qty: parseInt(i.qty, 10) }));

    if (parsedIngs.length === 0) {
      toast.error("You must add at least one ingredient to save the recipe.");
      return;
    }
    if (parsedIngs.some((i) => isNaN(i.item_id) || isNaN(i.qty) || i.qty <= 0)) {
      toast.error("Please ensure all ingredient quantities are valid positive numbers.");
      return;
    }

    createMutation.mutate(
      {
        name: name.trim(),
        output_item_id: parsedOutId,
        output_qty: parseInt(outQty, 10) || 1,
        ingredients: parsedIngs,
      },
      {
        onSuccess: () => {
          toast.success(`Saved recipe "${name.trim()}"!`);
          setName("");
          setOutId("");
          setOutQty("1");
          setIngs([{ id: "", qty: "1" }]);
        },
        onError: (err) => {
          toast.error(`Failed to save recipe: ${err.message}`);
        },
      }
    );
  };

  const handleDelete = (id: number, recipeName: string) => {
    deleteMutation.mutate(id, {
      onSuccess: () => {
        toast.info(`Deleted recipe "${recipeName}"`);
      },
      onError: (err) => {
        toast.error(`Failed to delete recipe: ${err.message}`);
      },
    });
  };

  return (
    <div className="card recipes-card">
      <div className="card-head">
        <div>
          <h2>Crafting &amp; Flipping Recipes</h2>
          <span className="muted" style={{ fontSize: "12px" }}>
            Track profit margins for potions, smithing, processing, and item combination flips
          </span>
        </div>
      </div>

      <div className="recipe-create-form">
        <div>
          <label className="field-label">RECIPE NAME</label>
          <input
            type="text"
            className="recipe-input"
            placeholder="e.g. Overload (4)"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        <div>
          <label className="field-label">OUTPUT ITEM</label>
          <ItemSearchInput
            value={outId}
            onChange={(id) => setOutId(id)}
            placeholder="Search finished item…"
            style={{ width: "100%" }}
            onSelect={(item) => {
              if (!name) setName(item.name);
            }}
          />
        </div>

        <div>
          <label className="field-label">QTY</label>
          <input
            type="number"
            className="recipe-input qty-input"
            value={outQty}
            min="1"
            onChange={(e) => setOutQty(e.target.value)}
          />
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          <label className="field-label">INGREDIENTS (ITEM &amp; QTY)</label>
          {ings.map((ing, idx) => (
            <div key={idx} style={{ display: "flex", gap: "6px", alignItems: "center" }}>
              <ItemSearchInput
                value={ing.id}
                onChange={(id) => {
                  const newIngs = [...ings];
                  newIngs[idx].id = id;
                  setIngs(newIngs);
                }}
                placeholder="Search ingredient…"
                style={{ flex: 1 }}
              />
              <input
                type="number"
                className="recipe-input qty-input"
                placeholder="Qty"
                value={ing.qty}
                min="1"
                onChange={(e) => {
                  const newIngs = [...ings];
                  newIngs[idx].qty = e.target.value;
                  setIngs(newIngs);
                }}
              />
              <button
                type="button"
                className="icon-btn danger"
                onClick={() => setIngs(ings.filter((_, i) => i !== idx))}
                title="Remove ingredient"
              >
                ✕
              </button>
            </div>
          ))}
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => setIngs([...ings, { id: "", qty: "1" }])}
            style={{ alignSelf: "flex-start", fontSize: "12px", marginTop: "2px" }}
          >
            + Add Ingredient
          </button>
        </div>

        <button
          type="button"
          className="btn btn-primary"
          onClick={handleAddRecipe}
          style={{ height: "38px", alignSelf: "end", marginBottom: "2px" }}
        >
          Save Recipe
        </button>
      </div>

      <div className="recipe-grid">
        {recipes.map((r) => {
          const roi = r.cost > 0 ? ((r.profit / r.cost) * 100).toFixed(1) : "0.0";
          return (
            <div key={r.id} className="recipe-card">
              <div className="recipe-header">
                <div className="recipe-title">
                  {r.output_icon && <img src={r.output_icon} alt="" className="item-icon sm" />}
                  <ItemTooltip
                    itemId={r.output_item_id}
                    name={r.output_name}
                    iconUrl={r.output_icon}
                    description={r.output_description}
                    members={r.output_members}
                    buyLimit={r.output_buy_limit}
                    highAlch={r.output_highalch}
                    buyPrice={r.output_buy_price}
                    sellPrice={r.output_sell_price}
                    wikiUrl={r.wiki_url}
                    enabled={tooltipsEnabled}
                  >
                    <span className="tooltip-target-text">{r.name}</span>
                  </ItemTooltip>
                </div>
                <button
                  className="icon-btn danger"
                  onClick={() => handleDelete(r.id, r.name)}
                  title="Delete Recipe"
                >
                  ✕
                </button>
              </div>

              <div className="recipe-flow">
                <div className="recipe-ing-list">
                  {r.ingredients.map((ing: RecipeIngredient, i: number) => (
                    <div key={i} className="recipe-ing">
                      <ItemTooltip
                        itemId={ing.item_id}
                        name={ing.name}
                        iconUrl={ing.icon_url}
                        description={ing.description}
                        members={ing.members}
                        buyLimit={ing.buy_limit}
                        highAlch={ing.highalch}
                        buyPrice={ing.input_buy_price}
                        sellPrice={ing.input_sell_price}
                        wikiUrl={ing.wiki_url}
                        enabled={tooltipsEnabled}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                          {ing.icon_url && <img src={ing.icon_url} alt="" className="item-icon sm" />}
                          <span className="muted" style={{ fontWeight: 600 }}>{ing.qty}x</span>
                          <span className="tooltip-target-text">{ing.name}</span>
                        </div>
                      </ItemTooltip>
                      <span className="muted tabular-nums" style={{ fontSize: "12.5px" }}>
                        {formatGP(ing.input_buy_price || 0)}
                      </span>
                    </div>
                  ))}
                  <div
                    className="recipe-ing"
                    style={{
                      borderTop: "1px solid var(--card-border)",
                      paddingTop: "6px",
                      marginTop: "4px",
                      fontWeight: 600,
                    }}
                  >
                    <span>Total Cost:</span>
                    <span className="tabular-nums" style={{ color: "var(--down)" }}>
                      -{formatGP(r.cost)}
                    </span>
                  </div>
                </div>
                <div className="recipe-arrow">➔</div>
                <div className="recipe-out">
                  <span className="muted" style={{ fontSize: "12px" }}>Produces {r.output_qty}x</span>
                  <ItemTooltip
                    itemId={r.output_item_id}
                    name={r.output_name}
                    iconUrl={r.output_icon}
                    description={r.output_description}
                    members={r.output_members}
                    buyLimit={r.output_buy_limit}
                    highAlch={r.output_highalch}
                    buyPrice={r.output_buy_price}
                    sellPrice={r.output_sell_price}
                    wikiUrl={r.wiki_url}
                    enabled={tooltipsEnabled}
                  >
                    <span style={{ fontWeight: 700, fontSize: "14px" }} className="tooltip-target-text">
                      {r.output_name}
                    </span>
                  </ItemTooltip>
                  <span className="tabular-nums" style={{ color: "var(--up)", fontSize: "13px", fontWeight: 700 }}>
                    +{formatGP(r.output_sell_price || 0)} ea
                  </span>
                </div>
              </div>

              <div className={`recipe-profit-badge ${r.profit > 0 ? "up" : r.profit < 0 ? "down" : ""}`}>
                Margin: {r.profit > 0 ? "+" : ""}
                {formatGP(r.profit)} ({roi}% ROI)
              </div>
            </div>
          );
        })}
        {recipes.length === 0 && (
          <div className="empty-hint muted" style={{ gridColumn: "1 / -1", textAlign: "center", padding: "32px" }}>
            No crafting recipes yet. Create one above to track crafting &amp; processing margins!
          </div>
        )}
      </div>
    </div>
  );
}
