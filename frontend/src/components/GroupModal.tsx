import { useState } from "react";
import { useToast } from "../context/ToastContext";

interface Props {
  open: boolean;
  itemId?: number | null;
  itemName?: string;
  onClose: () => void;
  onSave: (itemId: number | null, group: string) => void;
}

export default function GroupModal({ open, itemId = null, itemName = "", onClose, onSave }: Props) {
  const [groupName, setGroupName] = useState("");
  const { toast } = useToast();

  if (!open) return null;

  const isGroupOnly = itemId === null || itemId === 0;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = groupName.trim();
    if (!clean) {
      toast.error("Please enter an item group name.");
      return;
    }
    onSave(isGroupOnly ? null : itemId, clean);
    if (!isGroupOnly && itemName) {
      toast.success(`Moved ${itemName} to item group "${clean}"`);
    } else {
      toast.success(`Created item group "${clean}"`);
    }
    setGroupName("");
    onClose();
  };

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: "420px" }}>
        <div className="card-head">
          <h2 style={{ margin: 0 }}>
            {isGroupOnly ? "New Item Group" : "Move to Item Group"}
          </h2>
          <button className="icon-btn" onClick={onClose}>✕</button>
        </div>
        <p className="muted" style={{ fontSize: "12.5px", margin: "8px 0 14px" }}>
          {isGroupOnly
            ? "Create a dedicated dashboard to organize and track specific items together (e.g. Flipping, Herblore, High Alch, PVM)."
            : `Move ${itemName} to a custom item group.`}
        </p>
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          <input
            type="text"
            placeholder="e.g. Flipping, Boss Drops, Herblore…"
            value={groupName}
            onChange={(e) => setGroupName(e.target.value)}
            autoFocus
            style={{
              height: "38px",
              background: "var(--input-bg)",
              border: "1px solid var(--card-border)",
              color: "var(--fg)",
              borderRadius: "7px",
              padding: "0 10px",
              fontSize: "14px",
            }}
          />
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={!groupName.trim()}>
              {isGroupOnly ? "Create Item Group" : "Save Item Group"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
