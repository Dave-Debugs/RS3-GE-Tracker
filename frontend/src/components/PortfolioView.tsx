import { useState } from "react";
import {
  usePortfolio,
  useAddPortfolioItem,
  useClosePortfolioItem,
  useDeletePortfolioItem,
  useFlipHistory,
  useDeleteFlipHistory,
  useUpsertGeSlot,
  useGeSlots,
} from "../hooks";
import ItemSearchInput from "./ItemSearchInput";
import GeSlotsBoard from "./GeSlotsBoard";
import { formatGP, formatGPExact, parseGPInput, relativeTime } from "../lib/format";
import { useToast } from "../context/ToastContext";
import type { PortfolioItem } from "../types";

export default function PortfolioView() {
  const { data: stats, isLoading, error } = usePortfolio();
  const { data: historyData } = useFlipHistory();
  const { data: geSlots = [] } = useGeSlots();
  const addMutation = useAddPortfolioItem();
  const closeMutation = useClosePortfolioItem();
  const deleteMutation = useDeletePortfolioItem();
  const deleteFlipMutation = useDeleteFlipHistory();
  const upsertSlotMutation = useUpsertGeSlot();
  const { toast } = useToast();

  const [itemId, setItemId] = useState("");
  const [qty, setQty] = useState("");
  const [price, setPrice] = useState("");

  const [closingLot, setClosingLot] = useState<PortfolioItem | null>(null);
  const [closeSellPrice, setCloseSellPrice] = useState("");
  const [closeQty, setCloseQty] = useState("");
  const [closeNotes, setCloseNotes] = useState("");

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
    const parsedQty = parseGPInput(qty);
    const parsedPrice = parseGPInput(price);

    if (isNaN(parsedId)) {
      toast.error("Invalid item selected. Please choose an item from the dropdown.");
      return;
    }
    if (!parsedQty || parsedQty <= 0) {
      toast.error("Please enter a quantity greater than 0 (e.g. 1000 or 10k).");
      return;
    }
    if (parsedPrice === null || parsedPrice < 0) {
      toast.error("Please enter a valid buy price (e.g. 50k or 2.5m).");
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

  const openCloseModal = (item: PortfolioItem) => {
    setClosingLot(item);
    setCloseSellPrice(String(item.current_price || item.buy_price_per_item));
    setCloseQty(String(item.quantity));
    setCloseNotes("");
  };

  const handleConfirmClose = (e: React.FormEvent) => {
    e.preventDefault();
    if (!closingLot) return;
    const sPx = parseGPInput(closeSellPrice);
    const sQty = parseGPInput(closeQty);
    if (sPx === null || sPx < 0) {
      toast.error("Please enter a valid sell price.");
      return;
    }
    if (!sQty || sQty <= 0 || sQty > closingLot.quantity) {
      toast.error(`Quantity must be between 1 and ${closingLot.quantity.toLocaleString()}.`);
      return;
    }

    closeMutation.mutate(
      {
        port_id: closingLot.id,
        sell_price_per_item: sPx,
        quantity_sold: sQty,
        notes: closeNotes.trim() || undefined,
      },
      {
        onSuccess: (res) => {
          toast.success(
            `Sold ${sQty.toLocaleString()}x ${closingLot.name} for ${res.net_profit >= 0 ? "+" : ""}${formatGP(
              res.net_profit
            )} gp net profit!`
          );
          setClosingLot(null);
        },
        onError: (err) => toast.error(`Failed to close position: ${err.message}`),
      }
    );
  };

  const handleSendHoldingToSellSlot = (item: PortfolioItem) => {
    const emptySlot = geSlots.find((s) => s.empty);
    const targetSlot = emptySlot ? emptySlot.slot_index : 1;
    upsertSlotMutation.mutate(
      {
        slot_index: targetSlot,
        item_id: item.item_id,
        offer_type: "sell",
        target_price: item.current_price || item.break_even_price || item.buy_price_per_item,
        quantity: item.quantity,
        buy_cost_ref: item.buy_price_per_item,
        reset_timer: false,
      },
      {
        onSuccess: () => {
          toast.success(`Listed ${item.name} in GE Slot #${targetSlot} (Sell Offer)`);
        },
        onError: (err) => toast.error(`Failed to list in GE Slot: ${err.message}`),
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

  const netLiquidation = stats.net_liquidation_value ?? stats.current_value;
  const netUnrealized = stats.net_unrealized_profit ?? stats.unrealized_profit;
  const totalTax = stats.total_tax ?? 0;
  const netProfitPct =
    stats.total_cost > 0 ? ((netUnrealized / stats.total_cost) * 100).toFixed(2) : "0.00";

  const previewCloseSell = parseGPInput(closeSellPrice) ?? 0;
  const previewCloseQty = Math.min(
    closingLot?.quantity ?? 1,
    Math.max(1, parseGPInput(closeQty) ?? 1)
  );
  const previewCloseTaxPerItem =
    previewCloseSell >= 50 ? Math.min(Math.floor(previewCloseSell * 0.02), 50_000_000) : 0;
  const previewCloseNetProfit = closingLot
    ? (previewCloseSell - previewCloseTaxPerItem - closingLot.buy_price_per_item) * previewCloseQty
    : 0;

  return (
    <div>
      <GeSlotsBoard />

      <div className="card">
        <div
          className="portfolio-hero"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "16px",
            textAlign: "left",
          }}
        >
          <div>
            <div className="hero-label">Net Liquidation Value (After 2% Tax)</div>
            <div className="hero-value">{netLiquidation.toLocaleString()} gp</div>
            <div className="muted" style={{ fontSize: "12px", marginTop: "4px" }}>
              Gross: {stats.current_value.toLocaleString()} gp · Est. 2% Tax: -{formatGP(totalTax)} gp
            </div>
          </div>

          <div>
            <div className="hero-label">Unrealized Net P/L</div>
            <div
              className={`hero-profit ${
                netUnrealized > 0 ? "up" : netUnrealized < 0 ? "down" : "neutral"
              }`}
              style={{ fontSize: "22px", fontWeight: 700 }}
            >
              {netUnrealized > 0 ? "+" : ""}
              {netUnrealized.toLocaleString()} gp ({netProfitPct}%)
            </div>
            <div className="muted" style={{ fontSize: "12px", marginTop: "4px" }}>
              Total Cost Basis: {stats.total_cost.toLocaleString()} gp
            </div>
          </div>

          <div>
            <div className="hero-label">Realized Lifetime Profit</div>
            <div
              className={`hero-profit ${
                (historyData?.total_realized_profit ?? 0) > 0
                  ? "up"
                  : (historyData?.total_realized_profit ?? 0) < 0
                  ? "down"
                  : "neutral"
              }`}
              style={{ fontSize: "22px", fontWeight: 700 }}
            >
              {(historyData?.total_realized_profit ?? 0) > 0 ? "+" : ""}
              {(historyData?.total_realized_profit ?? 0).toLocaleString()} gp
            </div>
            <div className="muted" style={{ fontSize: "12px", marginTop: "4px" }}>
              {historyData?.trades_count ?? 0} closed flips · Win rate:{" "}
              <strong>{historyData?.win_rate_pct ?? 0}%</strong>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
          <h2>Open Holdings</h2>
          <span className="muted" style={{ fontSize: "12px" }}>
            Supports RS3 shorthand in inputs (e.g. <code>250k</code>, <code>12.5m</code>, <code>1.2b</code>)
          </span>
        </div>

        <form className="add-inline-form" onSubmit={handleAdd}>
          <label>
            Item
            <ItemSearchInput
              value={itemId}
              onChange={setItemId}
              onSelect={(item) => {
                if (item.sell_price && !price) {
                  setPrice(String(item.sell_price));
                } else if (item.current_price && !price) {
                  setPrice(String(item.current_price));
                }
                if (item.buy_limit && !qty) {
                  setQty(String(item.buy_limit));
                }
              }}
              placeholder="Search item (e.g. Abyssal whip)…"
              style={{ width: "100%" }}
            />
          </label>
          <label>
            Quantity (or 10k)
            <input
              type="text"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              required
              placeholder="e.g. 1000 or 10k"
            />
          </label>
          <label>
            Avg. Buy Price (GP or 2.5m)
            <input
              type="text"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              required
              placeholder="e.g. 50k or 2.5m"
            />
          </label>
          <button type="submit" className="btn btn-primary" style={{ height: "36px" }}>
            + Add Position
          </button>
        </form>

        {closingLot && (
          <form
            onSubmit={handleConfirmClose}
            style={{
              background: "var(--bg-soft)",
              border: "1px solid var(--accent)",
              borderRadius: "8px",
              padding: "14px",
              marginTop: "14px",
              display: "flex",
              flexDirection: "column",
              gap: "10px",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <strong>
                Sell / Close Position: {closingLot.name} (Bought @ {formatGPExact(closingLot.buy_price_per_item)} · Break-even:{" "}
                {formatGPExact(closingLot.break_even_price)})
              </strong>
              <button type="button" className="icon-btn" onClick={() => setClosingLot(null)}>
                ✕
              </button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1.5fr auto", gap: "10px", alignItems: "end" }}>
              <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px" }}>
                <span className="muted">Quantity Sold (Max {closingLot.quantity.toLocaleString()})</span>
                <input
                  type="text"
                  value={closeQty}
                  onChange={(e) => setCloseQty(e.target.value)}
                  required
                />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px" }}>
                <span className="muted">Sell Price / Item (GP or 2.5m)</span>
                <input
                  type="text"
                  value={closeSellPrice}
                  onChange={(e) => setCloseSellPrice(e.target.value)}
                  required
                />
              </label>
              <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px" }}>
                <span className="muted">Notes (Optional)</span>
                <input
                  type="text"
                  placeholder="e.g. Overnight flip"
                  value={closeNotes}
                  onChange={(e) => setCloseNotes(e.target.value)}
                />
              </label>
              <div style={{ display: "flex", gap: "8px" }}>
                <button type="submit" className="btn btn-primary" style={{ height: "36px" }}>
                  Confirm Sale ({previewCloseNetProfit >= 0 ? "+" : ""}
                  {formatGP(previewCloseNetProfit)} gp net)
                </button>
              </div>
            </div>
          </form>
        )}

        <div className="portfolio-rows" style={{ marginTop: "16px" }}>
          <div
            className="portfolio-row muted"
            style={{ fontSize: "11px", textTransform: "uppercase", borderBottom: "1px solid var(--card-border)" }}
          >
            <div />
            <div>Asset &amp; Break-Even</div>
            <div style={{ textAlign: "right" }}>Net Liquidation</div>
            <div style={{ textAlign: "right" }}>Live vs Avg Buy</div>
            <div style={{ textAlign: "right" }}>Net P/L (After 2% Tax)</div>
            <div style={{ textAlign: "right" }}>Actions</div>
          </div>
          {stats.items.map((item) => {
            const current = item.current_price || item.buy_price_per_item;
            const netProfit =
              item.lot_net_profit ??
              (current - (item.tax_per_item ?? 0) - item.buy_price_per_item) * item.quantity;
            const netVal = item.lot_net_value ?? current * item.quantity;
            const costBasis = item.buy_price_per_item * item.quantity;
            const roiPct = costBasis > 0 ? ((netProfit / costBasis) * 100).toFixed(2) : "0.00";
            return (
              <div key={item.id} className="portfolio-row">
                {item.icon_url || item.icon ? (
                  <img src={item.icon_url || item.icon || ""} alt="" className="item-icon sm" />
                ) : (
                  <span className="item-icon sm placeholder" />
                )}
                <div className="tracked-name">
                  <span className="name">{item.name}</span>
                  <span className="sub">
                    Break-even: {formatGP(item.break_even_price)} gp (2% tax)
                  </span>
                </div>
                <div className="tracked-price">
                  <div className="main-val">{formatGP(netVal)}</div>
                  <div className="sub">{item.quantity.toLocaleString()} units</div>
                </div>
                <div className="tracked-price">
                  <div className="main-val">{formatGP(current)}</div>
                  <div className="sub">Bought: {formatGP(item.buy_price_per_item)}</div>
                </div>
                <div
                  className="tracked-price"
                  style={{
                    color: netProfit > 0 ? "var(--up)" : netProfit < 0 ? "var(--down)" : "inherit",
                  }}
                >
                  <div className="main-val" style={{ color: "inherit" }}>
                    {netProfit > 0 ? "+" : ""}
                    {formatGP(netProfit)}
                  </div>
                  <div className="sub">
                    {netProfit > 0 ? "+" : ""}
                    {roiPct}% net
                  </div>
                </div>
                <div className="row-actions" style={{ display: "flex", gap: "6px", justifyContent: "flex-end" }}>
                  <button
                    type="button"
                    className="btn-mini btn-track-pill"
                    onClick={() => openCloseModal(item)}
                    title="Sell / Close Position & log to Realized Flip Ledger"
                  >
                    Sell / Close
                  </button>
                  <button
                    type="button"
                    className="btn-mini"
                    onClick={() => handleSendHoldingToSellSlot(item)}
                    title="List this holding in an active GE Slot"
                  >
                    → GE Slot
                  </button>
                  <button
                    className="icon-btn danger"
                    onClick={() => handleDelete(item.id, item.name)}
                    title="Delete Position without logging sale"
                  >
                    ✕
                  </button>
                </div>
              </div>
            );
          })}
          {stats.items.length === 0 && (
            <div className="empty-hint muted" style={{ textAlign: "center", padding: "28px" }}>
              No open positions. Add an item above or complete a Buy Offer from the 8-Slot GE Board.
            </div>
          )}
        </div>

        {/* Realized Flip Ledger */}
        <div style={{ marginTop: "28px", borderTop: "1px solid var(--card-border)", paddingTop: "20px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
            <div>
              <h2 style={{ margin: 0 }}>Realized Flip Ledger</h2>
              <span className="muted" style={{ fontSize: "12px" }}>
                Historical log of closed positions and completed GE slot flips (net of 2% GE tax)
              </span>
            </div>
            {historyData && historyData.trades_count > 0 && (
              <div className="muted" style={{ fontSize: "12px" }}>
                Total GE Tax Paid: <strong>-{formatGP(historyData.total_tax_paid)} gp</strong>
              </div>
            )}
          </div>

          {historyData && historyData.flips.length > 0 ? (
            <div className="table-scroll">
              <table className="table scanner-table">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th className="num">Qty</th>
                    <th className="num">Buy Price</th>
                    <th className="num">Sell Price</th>
                    <th className="num">2% Tax Paid</th>
                    <th className="num">Realized Net Profit</th>
                    <th className="num">ROI %</th>
                    <th className="num">Closed</th>
                    <th className="num">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {historyData.flips.map((f) => {
                    const isPos = f.net_profit >= 0;
                    return (
                      <tr key={f.id}>
                        <td className="item-cell">
                          <div className="scanner-item-wrap">
                            {f.icon_url ? (
                              <img src={f.icon_url} alt="" className="item-icon sm" />
                            ) : (
                              <span className="item-icon sm placeholder" />
                            )}
                            <div>
                              <span className="item-name">{f.name || `Item ${f.item_id}`}</span>
                              {f.notes && (
                                <div className="muted" style={{ fontSize: "11px" }}>
                                  {f.notes}
                                </div>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="num">{f.quantity.toLocaleString()}</td>
                        <td className="num">{formatGP(f.buy_price)}</td>
                        <td className="num">{formatGP(f.sell_price)}</td>
                        <td className="num muted">-{formatGP(f.tax_paid)}</td>
                        <td className={`num ${isPos ? "up" : "down"}`} style={{ fontWeight: 700 }}>
                          {isPos ? "+" : ""}
                          {formatGP(f.net_profit)}
                        </td>
                        <td className={`num ${isPos ? "up" : "down"}`}>
                          {isPos ? "+" : ""}
                          {f.roi_pct.toFixed(2)}%
                        </td>
                        <td className="num muted">{relativeTime(f.closed_at)}</td>
                        <td className="num">
                          <button
                            type="button"
                            className="icon-btn danger"
                            title="Delete flip log"
                            onClick={() => deleteFlipMutation.mutate(f.id)}
                          >
                            ✕
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-hint muted" style={{ textAlign: "center", padding: "20px" }}>
              No realized flips recorded yet. Click <strong>Sell / Close</strong> on any open holding or complete a Sell slot above!
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
