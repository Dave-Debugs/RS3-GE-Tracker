import React, { useState, useRef, useEffect } from "react";
import { formatGP, formatGPExact } from "../lib/format";

interface Props {
  itemId?: number;
  name: string;
  iconUrl?: string | null;
  description?: string | null;
  members?: boolean;
  buyLimit?: number | null;
  highAlch?: number | null;
  buyPrice?: number | null;
  sellPrice?: number | null;
  wikiUrl?: string;
  enabled?: boolean;
  children: React.ReactNode;
}

export default function ItemTooltip({
  itemId,
  name,
  iconUrl,
  description,
  members,
  buyLimit,
  highAlch,
  buyPrice,
  sellPrice,
  wikiUrl,
  enabled = true,
  children,
}: Props) {
  const [hovered, setHovered] = useState(false);
  const [position, setPosition] = useState<"top" | "bottom">("top");
  const [alignRight, setAlignRight] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const openTimerRef = useRef<number | null>(null);
  const closeTimerRef = useRef<number | null>(null);

  const handleMouseEnter = () => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }

    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setPosition(rect.top < 240 ? "bottom" : "top");
      setAlignRight(rect.left + 290 > window.innerWidth);
    }

    if (!hovered && !openTimerRef.current) {
      openTimerRef.current = window.setTimeout(() => {
        setHovered(true);
        openTimerRef.current = null;
      }, 100);
    }
  };

  const handleMouseLeave = () => {
    if (openTimerRef.current) {
      clearTimeout(openTimerRef.current);
      openTimerRef.current = null;
    }
    closeTimerRef.current = window.setTimeout(() => {
      setHovered(false);
      closeTimerRef.current = null;
    }, 350);
  };

  useEffect(() => {
    return () => {
      if (openTimerRef.current) clearTimeout(openTimerRef.current);
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    };
  }, []);

  if (!enabled) {
    return <>{children}</>;
  }

  const cleanWikiUrl = wikiUrl || `https://runescape.wiki/w/${encodeURIComponent(name.replace(/ /g, "_"))}`;

  return (
    <div
      ref={containerRef}
      className="item-tooltip-container"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={{ position: "relative", display: "inline-flex", alignItems: "center" }}
    >
      {children}

      {hovered && (
        <div
          className={`item-tooltip-card pos-${position} ${alignRight ? "align-right" : ""}`}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        >
          <div className="tooltip-head">
            {iconUrl ? (
              <img src={iconUrl} alt="" className="tooltip-icon" />
            ) : (
              <span className="tooltip-icon placeholder" />
            )}
            <div className="tooltip-title-area">
              <div className="tooltip-name">{name}</div>
              <div className="tooltip-sub">
                <span className={`badge-pill ${members ? "p2p" : "f2p"}`}>
                  {members ? "P2P Members" : "F2P"}
                </span>
                {buyLimit != null && (
                  <span className="badge-pill limit">Limit: {buyLimit.toLocaleString()}/4h</span>
                )}
              </div>
            </div>
          </div>

          {description && (
            <div className="tooltip-examine">
              <span className="examine-label">Examine:</span> "{description}"
            </div>
          )}

          <div className="tooltip-stats-grid">
            {buyPrice != null && (
              <div className="tooltip-stat">
                <span className="stat-label">Instant Buy:</span>
                <span className="stat-val">{formatGPExact(buyPrice)}</span>
              </div>
            )}
            {sellPrice != null && (
              <div className="tooltip-stat">
                <span className="stat-label">Instant Sell:</span>
                <span className="stat-val">{formatGPExact(sellPrice)}</span>
              </div>
            )}
            {highAlch != null && (
              <div className="tooltip-stat">
                <span className="stat-label">High Alch:</span>
                <span className="stat-val">{formatGP(highAlch)}</span>
              </div>
            )}
          </div>

          <a
            href={cleanWikiUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="tooltip-wiki-btn"
            onClick={(e) => e.stopPropagation()}
          >
            📖 How to Obtain &amp; Drops (RS3 Wiki) ↗
          </a>
        </div>
      )}
    </div>
  );
}
