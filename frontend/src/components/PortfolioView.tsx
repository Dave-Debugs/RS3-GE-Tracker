import { useState } from "react";
import { usePortfolio, useAddPortfolioItem, useDeletePortfolioItem } from "../hooks";
import ItemSearchInput from "./ItemSearchInput";
import { formatGP } from "../lib/format";
import { useToast } from "../context/ToastContext";

export default function PortfolioView() {
  const { data: stats, isLoading, error } = usePortfolio();
  const addMutation = useAddPortfolioItem();
  const deleteMutation = useDeletePortfolioItem();
  const { toast } = useToast();

  const [itemId, setItemId] = useState("");
  const [qty, setQty] = useState("");
  const [price, setPrice] = useState("");

  if (isLoading) return <div className="card"><p className="muted">Loading portfolio…</p></div>;
  if (error) return <div className="card"><p className="error-text">Error loading portfolio: {error.message}</p></div>;
  if (!stats) return null;

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault();
    if (!itemId) {
      toast.error("Please search and select an item first.");
      return;
    }
    const parsedId = parseInt(itemId, 10);
    const parsedQty = parseInt(qty, 10);
    const parsedPrice = parseInt(price, 10);

    if (isNaN(parsedId)) {
      toast.error("Invalid item selected. Please choose an item from the dropdown.");
      return;
    }
    if (isNaN(parsedQty) || parsedQty <= 0) {
      toast.error("Please enter a quantity greater than 0.");
      return;
    }
    if (isNaN(parsedPrice) || parsedPrice < 0) {
      toast.error("Please enter a valid buy price.");
      return;
    }

    addMutation.mutate(
      { item_id: parsedId, quantity: parsedQty, buy_price_per_item: parsedPrice },
      {
        onSuccess: () => {
          toast.success("Position added to portfolio!");
          setItemId("");
          setQty("");
          setPrice("");
        },
        onError: (err) => {
          toast.error(`Failed to add position: ${err.message}`);
        },
      }
    );
  };

  const handleDelete = (id: number, name: string) => {
    deleteMutation.mutate(id, {
      onSuccess: () => {
        toast.success(`Removed position for ${name}`);
      },
      onError: (err) => {
        toast.error(`Failed to delete position: ${err.message}`);
      },
    });
  };

  const profitPct =
    stats.total_cost > 0
      ? ((stats.unrealized_profit / stats.total_cost) * 100).toFixed(2)
      : "0.00";

  return (
    <div className="card">
      <div className="portfolio-hero">
        <div className="hero-label">Total Portfolio Value</div>
        <div className="hero-value">{stats.current_value.toLocaleString()} gp</div>
        <div
          className={`hero-profit ${
            stats.unrealized_profit > 0 ? "up" : stats.unrealized_profit < 0 ? "down" : "neutral"
          }`}
        >
          {stats.unrealized_profit > 0 ? "+" : ""}
          {stats.unrealized_profit.toLocaleString()} gp ({profitPct}%)
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
        <h2>Your Holdings</h2>
      </div>

      <form className="add-inline-form" onSubmit={handleAdd}>
        <label>
          Item
          <ItemSearchInput
            value={itemId}
            onChange={setItemId}
            onSelect={(item) => {
              if (item.current_price && !price) {
                setPrice(String(item.current_price));
              }
            }}
            placeholder="Search item (e.g. Abyssal whip)…"
            style={{ width: "100%" }}
          />
        </label>
        <label>
          Quantity
          <input
            type="number"
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            required
            min="1"
            placeholder="e.g. 1000"
          />
        </label>
        <label>
          Avg. Buy Price (GP)
          <input
            type="number"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            required
            min="0"
            placeholder="e.g. 50000"
          />
        </label>
        <button type="submit" className="btn btn-primary" style={{ height: "36px" }}>
          + Add Position
        </button>
      </form>

      <div className="portfolio-rows" style={{ marginTop: "16px" }}>
        <div
          className="portfolio-row muted"
          style={{ fontSize: "11px", textTransform: "uppercase", borderBottom: "1px solid var(--card-border)" }}
        >
          <div />
          <div>Asset</div>
          <div style={{ textAlign: "right" }}>Holdings</div>
          <div style={{ textAlign: "right" }}>Price</div>
          <div style={{ textAlign: "right" }}>P/L</div>
          <div />
        </div>
        {stats.items.map((item) => {
          const current = item.current_price || item.buy_price_per_item;
          const profit = (current - item.buy_price_per_item) * item.quantity;
          const totalVal = current * item.quantity;
          return (
            <div key={item.id} className="portfolio-row">
              {item.icon ? (
                <img src={item.icon} alt="" className="item-icon sm" />
              ) : (
                <span className="item-icon sm placeholder" />
              )}
              <div className="tracked-name">
                <span className="name">{item.name}</span>
                <span className="sub">ID: {item.item_id}</span>
              </div>
              <div className="tracked-price">
                <div className="main-val">{formatGP(totalVal)}</div>
                <div className="sub">{item.quantity.toLocaleString()} units</div>
              </div>
              <div className="tracked-price">
                <div className="main-val">{formatGP(current)}</div>
                <div className="sub">Avg: {formatGP(item.buy_price_per_item)}</div>
              </div>
              <div
                className="tracked-price"
                style={{
                  color: profit > 0 ? "var(--up)" : profit < 0 ? "var(--down)" : "inherit",
                }}
              >
                <div className="main-val" style={{ color: "inherit" }}>
                  {profit > 0 ? "+" : ""}
                  {formatGP(profit)}
                </div>
                <div className="sub">
                  {item.buy_price_per_item > 0
                    ? `${profit > 0 ? "+" : ""}${(((current - item.buy_price_per_item) / item.buy_price_per_item) * 100).toFixed(2)}%`
                    : "0%"}
                </div>
              </div>
              <div className="row-actions">
                <button
                  className="icon-btn danger"
                  onClick={() => handleDelete(item.id, item.name)}
                  title="Remove Position"
                >
                  ✕
                </button>
              </div>
            </div>
          );
        })}
        {stats.items.length === 0 && (
          <div className="empty-hint muted" style={{ textAlign: "center", padding: "32px" }}>
            No open positions. Add an item above to start tracking your portfolio.
          </div>
        )}
      </div>
    </div>
  );
}
