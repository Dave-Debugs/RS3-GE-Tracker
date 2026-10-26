import { useEffect, useState } from "react";
import { useGeSlots, useUpsertGeSlot, useCompleteGeSlot, useClearGeSlot } from "../hooks";
import ItemSearchInput from "./ItemSearchInput";
import { formatGP, formatDurationSeconds, parseGPInput } from "../lib/format";
import { useToast } from "../context/ToastContext";
import type { GeSlot } from "../types";

export default function GeSlotsBoard() {
  const { data: slots = [], isLoading } = useGeSlots();
  const upsertMut = useUpsertGeSlot();
  const completeMut = useCompleteGeSlot();
  const clearMut = useClearGeSlot();
  const { toast } = useToast();

  const [nowTick, setNowTick] = useState<number>(() => Math.floor(Date.now() / 1000));
  const [editingSlot, setEditingSlot] = useState<number | null>(null);
  const [itemId, setItemId] = useState<string>("");
  const [offerType, setOfferType] = useState<"buy" | "sell">("buy");
  const [targetPrice, setTargetPrice] = useState<string>("");
  const [buyCostRef, setBuyCostRef] = useState<string>("");
  const [qty, setQty] = useState<string>("1");

  useEffect(() => {
    const id = setInterval(() => {
      setNowTick(Math.floor(Date.now() / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, []);

  const openSlotEditor = (slot: GeSlot) => {
    setEditingSlot(slot.slot_index);
    if (!slot.empty && slot.item_id) {
      setItemId(String(slot.item_id));
      setOfferType(slot.offer_type || "buy");
      setTargetPrice(String(slot.target_price || ""));
      setBuyCostRef(slot.buy_cost_ref ? String(slot.buy_cost_ref) : "");
      setQty(String(slot.quantity || 1));
    } else {
      setItemId("");
      setOfferType("buy");
      setTargetPrice("");
      setBuyCostRef("");
      setQty("1");
    }
  };

  const handleSaveSlot = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingSlot) return;
    const parsedId = parseInt(itemId, 10);
    const parsedPrice = parseGPInput(targetPrice);
    const parsedQty = parseGPInput(qty);
    const parsedRef = parseGPInput(buyCostRef);

    if (isNaN(parsedId) || parsedId <= 0) {
      toast.error("Please select an item from the search dropdown.");
      return;
    }
    if (!parsedPrice || parsedPrice <= 0) {
      toast.error("Please enter a valid offer price (e.g. 2.5m or 500k).");
      return;
    }
    if (!parsedQty || parsedQty <= 0) {
      toast.error("Please enter a valid quantity.");
      return;
    }

    upsertMut.mutate(
      {
        slot_index: editingSlot,
        item_id: parsedId,
        offer_type: offerType,
        target_price: parsedPrice,
        quantity: parsedQty,
        buy_cost_ref: offerType === "sell" ? parsedRef : null,
        reset_timer: true,
      },
      {
        onSuccess: () => {
          toast.success(`Assigned GE Slot #${editingSlot}`);
          setEditingSlot(null);
        },
        onError: (err) => toast.error(`Failed to update slot: ${err.message}`),
      }
    );
  };

  const handleComplete = (slot: GeSlot, action: "portfolio" | "flip") => {
    completeMut.mutate(
      { slot_index: slot.slot_index, action },
      {
        onSuccess: () => {
          toast.success(
            action === "portfolio"
              ? `Slot #${slot.slot_index} (${slot.name}) moved to Portfolio holdings!`
              : `Slot #${slot.slot_index} (${slot.name}) logged to Realized Flip Ledger!`
          );
        },
        onError: (err) => toast.error(`Could not complete slot: ${err.message}`),
      }
    );
  };

  const handleResetTimer = (slot: GeSlot) => {
    if (!slot.item_id || !slot.target_price || !slot.quantity) return;
    upsertMut.mutate(
      {
        slot_index: slot.slot_index,
        item_id: slot.item_id,
        offer_type: slot.offer_type || "buy",
        target_price: slot.target_price,
        quantity: slot.quantity,
        buy_cost_ref: slot.buy_cost_ref,
        reset_timer: true,
      },
      {
        onSuccess: () => toast.info(`Reset 4-hour buy limit timer for Slot #${slot.slot_index}`),
      }
    );
  };

  if (isLoading) {
    return (
      <div className="card" style={{ marginBottom: "16px" }}>
        <p className="muted">Loading 8-Slot GE Board…</p>
      </div>
    );
  }

  const activeSlotsCount = slots.filter((s) => !s.empty).length;

  return (
    <section className="card" style={{ marginBottom: "16px" }}>
      <div className="card-head">
        <div>
          <h2 style={{ margin: 0, display: "inline-flex", alignItems: "center", gap: "8px" }}>
            8-Slot Grand Exchange Board
            <span className="count-badge">{activeSlotsCount} / 8</span>
          </h2>
          <div className="muted" style={{ fontSize: "12px", marginTop: "2px" }}>
            Track live Buy/Sell offers across all 8 in-game GE slots with 4-hour buy limit reset countdowns
          </div>
        </div>
      </div>

      {editingSlot !== null && (
        <form
          onSubmit={handleSaveSlot}
          style={{
            background: "var(--bg-soft)",
            border: "1px solid var(--card-border)",
            borderRadius: "8px",
            padding: "12px 14px",
            marginBottom: "14px",
            display: "grid",
            gridTemplateColumns:
              offerType === "sell"
                ? "110px 1.5fr 1fr 1fr 1fr auto"
                : "110px 1.6fr 1fr 1fr auto",
            gap: "10px",
            alignItems: "end",
          }}
        >
          <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px" }}>
            <span className="muted">Slot #{editingSlot} Type</span>
            <select
              value={offerType}
              onChange={(e) => setOfferType(e.target.value as "buy" | "sell")}
              style={{ height: "36px" }}
            >
              <option value="buy">Buy Offer</option>
              <option value="sell">Sell Offer</option>
            </select>
          </label>

          <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px" }}>
            <span className="muted">Item</span>
            <ItemSearchInput
              value={itemId}
              onChange={setItemId}
              onSelect={(it) => {
                if (offerType === "buy" && it.sell_price) setTargetPrice(String(it.sell_price));
                else if (offerType === "sell" && it.buy_price) {
                  setTargetPrice(String(it.buy_price));
                  if (!buyCostRef && it.sell_price) setBuyCostRef(String(it.sell_price));
                } else if (it.current_price) setTargetPrice(String(it.current_price));
                if (it.buy_limit) setQty(String(it.buy_limit));
              }}
              placeholder="Search item for GE Slot…"
              style={{ width: "100%" }}
            />
          </label>

          <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px" }}>
            <span className="muted">Offer Price (supports 10k/2.5m)</span>
            <input
              type="text"
              value={targetPrice}
              onChange={(e) => setTargetPrice(e.target.value)}
              placeholder="e.g. 1.5m"
              required
              style={{ height: "36px" }}
            />
          </label>

          {offerType === "sell" && (
            <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px" }}>
              <span className="muted">Avg Buy Cost / Item (for P&amp;L)</span>
              <input
                type="text"
                value={buyCostRef}
                onChange={(e) => setBuyCostRef(e.target.value)}
                placeholder="e.g. 1.4m"
                style={{ height: "36px" }}
              />
            </label>
          )}

          <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px" }}>
            <span className="muted">Quantity / 4h Limit</span>
            <input
              type="text"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              placeholder="e.g. 1000"
              required
              style={{ height: "36px" }}
            />
          </label>

          <div style={{ display: "flex", gap: "6px" }}>
            <button type="submit" className="btn btn-primary" style={{ height: "36px" }}>
              Save Slot #{editingSlot}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              style={{ height: "36px" }}
              onClick={() => setEditingSlot(null)}
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(245px, 1fr))",
          gap: "10px",
          marginTop: "8px",
        }}
      >
        {slots.map((slot) => {
          if (slot.empty) {
            return (
              <div
                key={slot.slot_index}
                onClick={() => openSlotEditor(slot)}
                style={{
                  border: "1px dashed var(--card-border)",
                  borderRadius: "8px",
                  padding: "14px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "center",
                  alignItems: "center",
                  minHeight: "120px",
                  cursor: "pointer",
                  background: "var(--bg-soft)",
                  opacity: 0.78,
                }}
              >
                <span className="muted" style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase" }}>
                  GE Slot #{slot.slot_index}
                </span>
                <span style={{ fontSize: "13px", fontWeight: 600, marginTop: "6px", color: "var(--accent)" }}>
                  + Assign Active Offer
                </span>
              </div>
            );
          }

          const resetAt = slot.limit_reset_at || 0;
          const remaining = Math.max(0, resetAt - nowTick);
          const isBuy = slot.offer_type === "buy";
          const marketComp = isBuy ? slot.market_sell : slot.market_buy;
          const undercut =
            isBuy && marketComp && slot.target_price
              ? marketComp > slot.target_price
              : !isBuy && marketComp && slot.target_price
              ? marketComp < slot.target_price
              : false;

          return (
            <div
              key={slot.slot_index}
              style={{
                border: "1px solid var(--card-border)",
                borderRadius: "8px",
                padding: "12px",
                background: "var(--bg-soft)",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                gap: "8px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span
                  className="pill"
                  style={{
                    fontSize: "10px",
                    padding: "2px 7px",
                    background: isBuy ? "rgba(152, 195, 121, 0.16)" : "rgba(232, 182, 76, 0.16)",
                    color: isBuy ? "var(--up)" : "var(--accent)",
                    fontWeight: 700,
                    textTransform: "uppercase",
                  }}
                >
                  Slot #{slot.slot_index} · {isBuy ? "BUY" : "SELL"}
                </span>
                <div style={{ display: "flex", gap: "4px" }}>
                  <button
                    type="button"
                    className="icon-btn"
                    title="Edit Slot"
                    onClick={() => openSlotEditor(slot)}
                    style={{ fontSize: "11px" }}
                  >
                    ✎
                  </button>
                  <button
                    type="button"
                    className="icon-btn danger"
                    title="Clear Slot"
                    onClick={() => clearMut.mutate(slot.slot_index)}
                    style={{ fontSize: "11px" }}
                  >
                    ✕
                  </button>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                {slot.icon_url ? (
                  <img src={slot.icon_url} alt="" className="item-icon sm" />
                ) : (
                  <span className="item-icon sm placeholder" />
                )}
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div
                    style={{
                      fontWeight: 700,
                      fontSize: "13px",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                    title={slot.name}
                  >
                    {slot.name}
                  </div>
                  <div className="muted" style={{ fontSize: "11px" }}>
                    {slot.quantity?.toLocaleString()}x @ {formatGP(slot.target_price)} gp
                  </div>
                </div>
              </div>

              <div
                style={{
                  fontSize: "11.5px",
                  display: "flex",
                  justifyContent: "space-between",
                  padding: "5px 8px",
                  borderRadius: "6px",
                  background: "var(--card)",
                }}
              >
                <span className="muted">4h Limit Timer:</span>
                <strong
                  style={{
                    color: remaining === 0 ? "var(--up)" : "var(--accent)",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {formatDurationSeconds(remaining)}
                </strong>
              </div>

              {marketComp != null && (
                <div style={{ fontSize: "11px", display: "flex", justifyContent: "space-between" }}>
                  <span className="muted">Live {isBuy ? "Insta-Sell" : "Insta-Buy"}:</span>
                  <span className={undercut ? "down" : "up"} style={{ fontWeight: 600 }}>
                    {formatGP(marketComp)} gp {undercut ? "(Outbid)" : "(Competitive)"}
                  </span>
                </div>
              )}

              <div style={{ display: "flex", gap: "6px", marginTop: "2px" }}>
                {isBuy ? (
                  <button
                    type="button"
                    className="btn-mini btn-track-pill"
                    style={{ flex: 1 }}
                    onClick={() => handleComplete(slot, "portfolio")}
                    title="Move bought items into Portfolio Holdings"
                  >
                    ✓ Bought → Portfolio
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn-mini btn-track-pill"
                    style={{ flex: 1 }}
                    onClick={() => handleComplete(slot, "flip")}
                    title="Log completed sale in Realized Flip Ledger"
                  >
                    ✓ Sold → Flip Ledger
                  </button>
                )}
                <button
                  type="button"
                  className="btn-mini"
                  onClick={() => handleResetTimer(slot)}
                  title="Restart 4-hour buy limit timer"
                >
                  ↻ 4h
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
