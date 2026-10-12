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
  description?: string | null;
  members: boolean;
  buy_limit?: number | null;
  highalch?: number | null;
  favorite: boolean;
  current_price: number | null;
  buy_price: number | null;
  sell_price: number | null;
  margin: number | null;
  tax: number | null;
  net_profit: number | null;
  roi_pct?: number | null;
  limit_profit_4h?: number | null;
  change_24h: number | null;
  change_7d: number | null;
  trend: string;
  volume_24h: number;
  last_updated: number | null;
  backfilled: boolean;
  group_name: string;
}

export interface FlipScannerItem {
  item_id: number;
  name: string;
  icon: string | null;
  icon_url: string | null;
  wiki_url: string;
  description: string | null;
  members: boolean;
  buy_limit: number | null;
  highalch: number | null;
  buy_price: number;
  sell_price: number;
  margin: number;
  tax: number;
  net_profit: number;
  roi_pct: number;
  limit_profit_4h: number;
  volume_24h: number;
  last_updated: number | null;
}

export interface AlchScannerItem {
  item_id: number;
  name: string;
  icon: string | null;
  icon_url: string | null;
  wiki_url: string;
  description: string | null;
  members: boolean;
  buy_limit: number | null;
  highalch: number;
  buy_price: number;
  sell_price: number;
  nature_rune_price: number;
  net_profit: number;
  roi_pct: number;
  limit_profit_4h: number;
  volume_24h: number;
  last_updated: number | null;
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

export interface SettingsPayload {
  update_interval_minutes: "5" | "10" | "15" | "30" | "60";
  theme: "dark" | "light";
  default_chart_range: ChartRange;
  user_agent: string;
  collector_autostart: "true" | "false";
}

export interface PortfolioItem {
  id: number;
  item_id: number;
  name: string;
  icon: string | null;
  icon_url?: string | null;
  quantity: number;
  buy_price_per_item: number;
  current_price: number | null;
}

export interface PortfolioStats {
  items: PortfolioItem[];
  total_cost: number;
  current_value: number;
  unrealized_profit: number;
}

export interface RecipeIngredient {
  item_id: number;
  name: string;
  icon: string | null;
  icon_url?: string | null;
  description?: string | null;
  members?: boolean;
  buy_limit?: number | null;
  highalch?: number | null;
  input_buy_price: number | null;
  input_sell_price?: number | null;
  wiki_url?: string;
  qty: number;
}

export interface Recipe {
  id: number;
  name: string;
  output_item_id: number;
  output_name: string;
  output_icon: string | null;
  output_description?: string | null;
  output_members?: boolean;
  output_buy_limit?: number | null;
  output_highalch?: number | null;
  output_qty: number;
  output_sell_price: number | null;
  output_buy_price?: number | null;
  wiki_url?: string;
  cost: number;
  revenue: number;
  profit: number;
  ingredients: RecipeIngredient[];
}

export interface Alert {
  id: number;
  item_id: number;
  name?: string;
  icon_url?: string | null;
  condition: string;
  threshold_price: number;
  active: boolean;
  last_triggered: number | null;
  current_price?: number | null;
  latest_high?: number | null;
  latest_low?: number | null;
}

export interface Settings {
  update_interval_minutes: string;
  theme: string;
  default_chart_range: string;
  show_item_tooltips?: string;
  user_agent: string;
  collector_autostart: string;
  database_path: string;
}

export interface UpdateCheckResult {
  update_available: boolean;
  current_version: string;
  latest_version?: string;
  tag_name?: string;
  download_url?: string | null;
  checksum_url?: string | null;
  asset_name?: string | null;
  release_url?: string;
  error?: string;
}

export type ChartRange = "1h" | "6h" | "24h" | "7d" | "14d" | "30d";
export type ChartMode = "price" | "percent";

