export interface SearchResult {
  item_id: number;
  name: string;
  description: string | null;
  members: boolean;
  icon_url: string | null;
  buy_limit: number | null;
  current_price: number | null;
  buy_price: number | null;
  sell_price: number | null;
}

export interface TrackedItem {
  item_id: number;
  name: string;
  icon_url: string | null;
  members: boolean;
  favorite: boolean;
  current_price: number | null;
  buy_price: number | null;
  sell_price: number | null;
  change_24h: number | null;
  change_7d: number | null;
  trend: string;
  volume_24h: number;
  last_updated: number | null;
  backfilled: boolean;
  group_name: string;
}

export interface PricePoint {
  timestamp: number;
  high_price: number | null;
  low_price: number | null;
  average_price: number | null;
  volume: number;
}

export interface PriceSeries {
  item_id: number;
  name: string;
  range: string;
  points: PricePoint[];
  moving_averages: Record<string, { timestamp: number; value: number }[]>;
}

export interface ItemStats {
  item_id: number;
  current_price: number | null;
  change_24h: number | null;
  change_7d: number | null;
  high_7d: number | null;
  low_7d: number | null;
  average_7d: number | null;
  median_7d: number | null;
  volatility_7d: number | null;
  total_volume: number;
  points: number;
}

export interface TrendInfo {
  item_id: number;
  classification: string;
  slope_pct_per_day: number;
  short_ma: number | null;
  long_ma: number | null;
  momentum_pct: number;
  volatility_pct: number;
  r_squared: number;
  points_used: number;
}

export interface Mover {
  item_id: number;
  name: string;
  icon_url: string | null;
  current_price: number | null;
  previous_price?: number;
  change_pct?: number;
  volume_24h: number;
}

export interface MoversResponse {
  period: string;
  gainers: Mover[];
  losers: Mover[];
  highest_volume: Mover[];
}

export interface StatusInfo {
  api_online: boolean;
  collector_running: boolean;
  last_update: number | null;
  next_update: number | null;
  last_run_ok: boolean;
  last_run_error: string | null;
  tracked_items: number;
  database_records: number;
  data_coverage_days: number;
  item_count: number;
  server_time: number;
}

export interface Settings {
  update_interval_minutes: string;
  theme: string;
  default_chart_range: string;
  user_agent: string;
  collector_autostart: string;
  database_path: string;
}

export type ChartRange = "1h" | "6h" | "24h" | "7d" | "14d";
export type ChartMode = "price" | "percent";
