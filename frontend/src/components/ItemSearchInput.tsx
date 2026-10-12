import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { SearchResult } from "../types";
import { formatGP } from "../lib/format";
import recipeDbJson from "../recipes.json";

const RECIPE_DB = recipeDbJson as Record<string, any>;

interface Props {
  value: string;
  onChange: (id: string) => void;
  onSelect?: (item: SearchResult) => void;
  placeholder?: string;
  className?: string;
  style?: React.CSSProperties;
  onlyWithRecipes?: boolean;
}

export default function ItemSearchInput({
  value,
  onChange,
  onSelect,
  placeholder,
  className,
  style,
  onlyWithRecipes,
}: Props) {
  const [query, setQuery] = useState("");
  const [selectedItem, setSelectedItem] = useState<SearchResult | null>(null);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<number>();

  useEffect(() => {
    if (!value) {
      setSelectedItem(null);
      setQuery("");
      return;
    }
    if (selectedItem?.item_id !== Number(value)) {
      api.search(String(value)).then(({ results: apiResults }) => {
        const found = apiResults.find((r) => String(r.item_id) === String(value)) || apiResults[0];
        if (found) {
          setSelectedItem(found);
          setQuery(found.name);
          if (onSelect) onSelect(found);
        } else {
          setQuery(`Item ${value}`);
        }
      }).catch(() => {
        setQuery(`Item ${value}`);
      });
    }
  }, [value]);

  useEffect(() => {
    window.clearTimeout(debounceRef.current);
    if (!open) return;

    if (query.trim().length < 2 && isNaN(Number(query.trim()))) {
      setResults([]);
      return;
    }

    debounceRef.current = window.setTimeout(async () => {
      setLoading(true);
      try {
        const { results: apiResults } = await api.search(query.trim());
        if (onlyWithRecipes) {
          setResults(apiResults.filter((r) => RECIPE_DB[String(r.item_id)]));
        } else {
          setResults(apiResults);
        }
      } catch {
      } finally {
        setLoading(false);
      }
    }, 200);
    return () => window.clearTimeout(debounceRef.current);
  }, [query, open, onlyWithRecipes]);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const handleSelectItem = (r: SearchResult) => {
    setSelectedItem(r);
    setQuery(r.name);
    onChange(String(r.item_id));
    if (onSelect) onSelect(r);
    setOpen(false);
  };

  const handleClear = () => {
    setSelectedItem(null);
    setQuery("");
    onChange("");
    setResults([]);
  };

  return (
    <div className="search-box" style={{ marginBottom: 0, position: "relative", ...style }} ref={boxRef}>
      <div
        className="search-input-wrap"
        style={{
          padding: "0 8px",
          minHeight: "36px",
          borderRadius: "7px",
          display: "flex",
          alignItems: "center",
          gap: "6px",
        }}
      >
        {selectedItem?.icon_url ? (
          <img src={selectedItem.icon_url} alt="" className="item-icon sm" style={{ width: "20px", height: "20px" }} />
        ) : (
          <span style={{ opacity: 0.5, fontSize: "13px" }}>🔍</span>
        )}
        <input
          className={`search-input ${className || ""}`}
          placeholder={placeholder || "Search item…"}
          value={query}
          style={{ padding: "6px 0", fontSize: "13px" }}
          onChange={(e) => {
            setQuery(e.target.value);
            setSelectedItem(null);
            setOpen(true);
            if (/^\d+$/.test(e.target.value.trim())) {
              onChange(e.target.value.trim());
            }
          }}
          onFocus={() => {
            setOpen(true);
          }}
        />
        {loading && <span className="search-spinner" style={{ fontSize: "12px" }}>…</span>}
        {(query || selectedItem) && (
          <button
            type="button"
            className="icon-btn"
            style={{ padding: "2px 4px", fontSize: "12px" }}
            onClick={handleClear}
            title="Clear"
          >
            ✕
          </button>
        )}
      </div>

      {open && results.length > 0 && (
        <div className="search-dropdown" style={{ top: "100%", maxHeight: "220px", zIndex: 50 }}>
          {results.map((r) => (
            <div
              key={r.item_id}
              className="search-row clickable-row"
              style={{ cursor: "pointer", padding: "7px 10px", display: "flex", alignItems: "center", gap: "8px" }}
              onClick={() => handleSelectItem(r)}
            >
              {r.icon_url ? (
                <img src={r.icon_url} alt="" className="item-icon sm" />
              ) : (
                <span className="item-icon sm placeholder" />
              )}
              <div className="search-meta" style={{ flex: 1 }}>
                <span className="search-name" style={{ fontSize: "13px" }}>{r.name}</span>
                <span className="muted" style={{ fontSize: "11px" }}>
                  ID {r.item_id} {r.members ? "· Members" : ""}
                </span>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: "12.5px", fontWeight: 600, color: "var(--accent)" }}>
                  {r.current_price ? formatGP(r.current_price) : "—"}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
