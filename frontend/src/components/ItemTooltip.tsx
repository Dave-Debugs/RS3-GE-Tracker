import React, { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
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
  const [coords, setCoords] = useState<{
    top: number;
    left: number;
    placement: "top" | "bottom";
  }>({ top: 0, left: 0, placement: "top" });

  const containerRef = useRef<HTMLDivElement>(null);
  const openTimerRef = useRef<number | null>(null);
  const closeTimerRef = useRef<number | null>(null);

  const updatePosition = useCallback(() => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const cardWidth = 310;
    const showBelow = rect.top < 250;
    const left = Math.max(
      12,
      Math.min(rect.left, window.innerWidth - cardWidth - 16)
    );
    const top = showBelow ? rect.bottom + 8 : rect.top - 8;
    setCoords({
      top,
      left,
      placement: showBelow ? "bottom" : "top",
    });
  }, []);

  const handleMouseEnter = () => {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }

    updatePosition();

    if (!hovered && !openTimerRef.current) {
      openTimerRef.current = window.setTimeout(() => {
        updatePosition();
        setHovered(true);
        openTimerRef.current = null;
      }, 90);
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
    }, 220);
  };

  useEffect(() => {
    if (!hovered) return;
    const handleScrollOrResize = () => updatePosition();
    window.addEventListener("scroll", handleScrollOrResize, true);
    window.addEventListener("resize", handleScrollOrResize);
    return () => {
      window.removeEventListener("scroll", handleScrollOrResize, true);
      window.removeEventListener("resize", handleScrollOrResize);
    };
  }, [hovered, updatePosition]);

  useEffect(() => {
    return () => {
      if (openTimerRef.current) clearTimeout(openTimerRef.current);
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    };
  }, []);

  if (!enabled) {
    return <>{children}</>;
  }

  const cleanWikiUrl =
    wikiUrl || `https://runescape.wiki/w/${encodeURIComponent(name.replace(/ /g, "_"))}`;

  return (
    <div
      ref={containerRef}
      className="item-tooltip-container"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={{ position: "relative", display: "inline-flex", alignItems: "center" }}
    >
      {children}

      {hovered &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            className={`item-tooltip-card portal-${coords.placement}`}
            style={{
              position: "fixed",
              top: `${coords.top}px`,
              left: `${coords.left}px`,
              transform: coords.placement === "top" ? "translateY(-100%)" : "none",
              zIndex: 99999,
            }}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
            onClick={(e) => e.stopPropagation()}
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
                <span className="examine-label">Examine:</span> &ldquo;{description}&rdquo;
              </div>
            )}

            <div className="tooltip-stats-grid">
              {buyPrice != null && (
                <div className="tooltip-stat">
                  <span className="stat-label">Instant Buy</span>
                  <span className="stat-val">{formatGPExact(buyPrice)}</span>
                </div>
              )}
              {sellPrice != null && (
                <div className="tooltip-stat">
                  <span className="stat-label">Instant Sell</span>
                  <span className="stat-val">{formatGPExact(sellPrice)}</span>
                </div>
              )}
              {highAlch != null && (
                <div className="tooltip-stat">
                  <span className="stat-label">High Alch</span>
                  <span className="stat-val">{formatGP(highAlch)} gp</span>
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
          </div>,
          document.body
        )}
    </div>
  );
}
