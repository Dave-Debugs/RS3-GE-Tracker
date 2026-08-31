import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { SearchResult } from "../types";
import { formatGP } from "../lib/format";

interface Props {
  trackedIds: Set<number>;
  onTrack: (item: SearchResult) => void;
  onSelect: (item: SearchResult) => void;
}

export default function SearchBar({ trackedIds, onTrack, onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<number>();

  useEffect(() => {
    window.clearTimeout(debounceRef.current);
    if (query.trim().length < 2) {
      setResults([]);
      setOpen(false);
      return;
    }
    debounceRef.current = window.setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const { results } = await api.search(query.trim());
        setResults(results);
        setOpen(true);
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => window.clearTimeout(debounceRef.current);
  }, [query]);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  return (
    <div className="search-box" ref={boxRef}>
      <div className="search-input-wrap">
        <span className="search-icon">🔍</span>
        <input
          id="global-search-input"
          className="search-input"
          placeholder="Search Grand Exchange items… (Press / to search)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => results.length && setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Escape") setOpen(false);
          }}
        />
        {loading && <span className="search-spinner">…</span>}
      </div>
      {open && (
        <div className="search-dropdown">
          {error && <div className="search-row muted">Search failed: {error}</div>}
          {!error && !results.length && (
            <div className="search-row muted">No matching items</div>
          )}
          {results.map((r) => (
            <div key={r.item_id} className="search-row clickable-row" onClick={() => { onSelect(r); setOpen(false); }}>
              {r.icon_url ? (
                <img src={r.icon_url} alt="" className="item-icon"
                     loading="lazy"
                     onError={(e) => ((e.target as HTMLImageElement).style.visibility = "hidden")} />
              ) : (
                <span className="item-icon placeholder" />
              )}
              <div className="search-meta">
                <span className="search-name">{r.name}</span>
                <span className="search-id">
                  ID {r.item_id}{r.members ? " · Members" : ""}
                </span>
              </div>
              <div className="search-price" style={{ textAlign: "right" }}>
                <div>{formatGP(r.current_price)}</div>
                <div style={{ fontSize: "0.8em", color: "var(--text-muted)" }}>
                  B: {r.buy_price ? formatGP(r.buy_price) : "-"} | S: {r.sell_price ? formatGP(r.sell_price) : "-"}
                </div>
              </div>
              <div className="search-actions" style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                {!trackedIds.has(r.item_id) ? (
                  <button className="btn btn-track" onClick={(e) => { e.stopPropagation(); onTrack(r); setOpen(false); }}>+ Track</button>
                ) : (
                  <span className="tracked-tag">Tracked</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
