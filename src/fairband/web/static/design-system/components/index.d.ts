/**
 * Fairband components (window.Fairband).
 *
 * Every component is presentational: it takes data and renders it. None of
 * them fetch, compute, sort or format a date into something other than what
 * the engine produced. Pass dates as ISO strings and numbers as numbers.
 */

/** Damodaran's six life-cycle phases, 1 = Start-up through 6 = Decline. */
export type Phase = 1 | 2 | 3 | 4 | 5 | 6;

/**
 * Who made a write. Sits on overrides, proposals, trades and policy edits —
 * never on a computed number, because the engine writes every value.
 */
export type Principal = 'owner' | 'agent' | 'system';

/**
 * Which inputs went into a computed number. `mechanical` = the system's own
 * inputs only; `reviewed` = one or more overrides are inside. It follows the
 * inputs in *this* number, not whether anyone ever touched the company.
 */
export type Basis = 'mechanical' | 'reviewed';

/** Where today sits relative to the value's validity window. */
export type Freshness = 'current' | 'aging' | 'expired';

/**
 * fairband: the price against the value at belief, in five bands (classifier-designation spec
 * 7.1). The engine's word, carried on the row; a component never derives it.
 */
export type Designation = 'well-below' | 'below' | 'near' | 'above' | 'well-above';

export interface MarkProps {
  /** Edge length in px. Square. Default 24. Below 20 the three bands fuse. */
  size?: number;
  /** `ink` draws it in one ink, for a ground the three colours cannot sit on. */
  tone?: 'colour' | 'ink';
  /** Accessible name. Pass `null` when a wordmark beside it already says it. */
  label?: string | null;
  className?: string;
}

export interface RunProgressProps {
  /** Size of the universe this run covers. 0 renders nothing. */
  total: number;
  /** Companies valued so far. */
  done: number;
  /** Companies the run could not value. */
  failed?: number;
  /** Pending is derived: total - done - failed. Never passed in. */
  /** A short lowercase verb phrase; `valuing` by default. */
  stage?: string;
  /** Makes the failed count a button. Wire it to showing those companies. */
  onShowFailed?: () => void;
  /** The header form: a fixed-width track and `2,841 of 4,112`. */
  compact?: boolean;
  className?: string;
}

/** What AppHeader needs to show a run in place of the engine stamp. */
export interface AppHeaderRun {
  total: number;
  done: number;
  failed?: number;
  stage?: string;
  onShowFailed?: () => void;
}

export interface AppHeaderView {
  id: string;
  label: string;
  /** A waiting count, e.g. proposals in the inbox. Omit or 0 renders nothing. */
  count?: number;
}

export interface AppHeaderProps {
  views?: AppHeaderView[];
  /** The `id` of the current view. */
  view?: string;
  onViewChange?: (id: string) => void;
  /** ISO timestamp of the last engine run. Rendered `29 Oct 2026, 03:12`. */
  engineRanAt?: string;
  /** A run in progress. Replaces `engineRanAt` while it is set, because the
      stamp describes the last finished run. */
  run?: AppHeaderRun;
  /** Overrides the wordmark. There is no reason to. */
  name?: string;
  /** Extra controls, placed left of the engine stamp. */
  children?: unknown;
  className?: string;
}

export interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'quiet' | 'danger';
  size?: 'sm' | 'md';
  disabled?: boolean;
  type?: 'button' | 'submit' | 'reset';
  onClick?: (event: unknown) => void;
  /** fairband: a menu's toggle passes whether its menu is open; it reaches the button. */
  'aria-expanded'?: 'true' | 'false';
  /** fairband: the control's name in full, where its text is short (Top ↑ is "Back to top"). */
  'aria-label'?: string;
  className?: string;
  children?: unknown;
}

export interface PhaseBadgeProps {
  /** fairband: `null` when the engine could not classify the company; renders an em dash. */
  phase: Phase | null;
  /** A shorter synonym only — never a different taxonomy. */
  label?: string;
  showLabel?: boolean;
  size?: 'sm' | 'md';
}

export interface PrincipalChipProps {
  principal: Principal;
  /** The agent's role: the model identifier it connected under, e.g. `claude-opus-5`. */
  actor?: string;
  /** The author's reason, verbatim. Shown as the chip's title. */
  reason?: string;
  /** ISO date or timestamp; rendered as `3 Dec 2026` with ISO in `datetime`. */
  at?: string;
  /** Gives the chip the prov-input-quiet ground, for a report header. */
  weight?: 'strong';
  /** Drops the border and ground, for a table cell. */
  compact?: boolean;
}

export interface BasisChipProps {
  basis: Basis;
  compact?: boolean;
  /** Drops the ƒ where the surrounding context already carries one. */
  showGlyph?: boolean;
}

export interface ValueCellProps {
  /** A number; formatted as money. With `format: 'plain'`, an already-formatted string. */
  value: number | string;
  format?: 'money' | 'plain';
  basis: Basis;
  freshness?: Freshness;
  /** `strong` uses figure-lg, for the single headline number on a detail view. */
  emphasis?: 'normal' | 'strong';
  align?: 'left' | 'right';
  /** Hide the basis word where a column header already names it. */
  showBasis?: boolean;
  asOf?: string;
  observedAt?: string;
  enteredAt?: string;
  showDates?: boolean;
}

export interface Override {
  /** The MCP tag that was overridden. */
  tag: string;
  /** Already-formatted: these may be percentages, multiples or money. */
  from: string;
  to: string;
  /** This override's contribution to the reviewed value, in the same unit as `mechanical`. */
  delta: number;
  principal: Principal;
  actor?: string;
  reason?: string;
}

export interface ValueBridgeProps {
  mechanical: number;
  reviewed: number;
  /** In the order they apply. Reordering them would misstate which input did what. */
  overrides: Override[];
  note?: string;
}

export interface BandMeterProps {
  /** The fair band, per share. */
  low: number;
  high: number;
  /** The market price, per share. fairband: no word is derived from it; see `designation`. */
  price: number;
  /** The point estimate inside the band. Defaults to the band's midpoint. */
  fairValue?: number;
  /** The thresholds that bound the buy and trim zones. */
  buyLevel?: number;
  trimLevel?: number;
  width?: number;
  /** `false` hides the three threshold labels below the track. */
  showScale?: boolean;
  caption?: string;
  /** fairband: the row's word, shown in the head; `null` or absent shows none. */
  designation?: Designation | null;
}

export interface ValidityWindowProps {
  asOf: string;
  observedAt: string;
  enteredAt: string;
  validFrom: string;
  validUntil: string;
  /** The engine's clock, never the browser's. Defaults to `enteredAt`. */
  today?: string;
  tag?: string;
}

export interface TaggedInputProps {
  label: string;
  /** The stable MCP tag, e.g. `growth.rev_cagr_5y`. Agents address this string. */
  tag: string;
  value: string | number;
  unit?: string;
  /** Required before the change can be saved. */
  reason?: string;
  /** Defaults to `owner`. */
  principal?: Principal;
  actor?: string;
  locked?: boolean;
  onChange?: (event: unknown) => void;
}

/** An agent writes three kinds of record; only a proposal waits for the Owner. */
export type OverrideState =
  | 'applied'
  | 'refused-locked'
  | 'refused-evidence'
  | 'refused-unit'
  | 'refused-not-input'
  | 'conflict-stale';

/** `lasting` stays until an updated valuation is asked for; `period-tied` ends with its period. */
export type Lifetime = 'lasting' | 'period-tied';

export interface EvidenceItem {
  /** A source document, a finding, a base rate, or a URL the server stores as text. */
  kind: 'document' | 'finding' | 'base rate' | 'url' | string;
  ref: string;
  note?: string;
}

export interface OverrideRecordProps {
  /** The input's tagged path, e.g. `wacc.erp`. One input per record. */
  tag: string;
  /** Already formatted: these may be percentages, multiples or money. */
  from: string;
  to: string;
  lifetime?: Lifetime;
  /** The period or data point a period-tied override ends with. */
  period?: string;
  reason?: string;
  /** Required on an override, unlike on a note. */
  evidence?: EvidenceItem[];
  principal?: Principal;
  actor?: string;
  /** Default `applied`. The server has already decided by the time this renders. */
  state?: OverrideState;
  /** On anything but `applied`: the rule that stopped it, in terms the agent can act on. */
  message?: string;
  revisionFrom?: string;
  revisionTo?: string;
  /** On `applied`: the effect on the value, per share. */
  effect?: number;
  reviewed?: number;
  validUntil?: string;
}

/** A plain string, or a number that traces to a stored fact or an engine metric. */
export type ReportPart = string | { cite: string; ref: string };

export interface ReportSection {
  heading?: string;
  parts: ReportPart[];
}

export interface ReportFinding {
  /** Section, paragraph and citation index — the agent has to find the one number. */
  where: string;
  /** The server's words: unresolved reference · wrong unit · wrong period · wrong snapshot · a number with no reference · a derived figure the engine has not emitted. */
  what: string;
  detail?: string;
}

export interface ReportReaderProps {
  mode?: 'valuation review' | 'full report';
  state?: 'published' | 'rejected';
  revision?: string;
  cites?: {
    snapshot?: string;
    review?: string;
    thesis?: string;
    /** The date of the full report a valuation review reuses. */
    reusesFullReportOf?: string;
  };
  sections?: ReportSection[];
  /** On `rejected`. The published report is unchanged either way. */
  findings?: ReportFinding[];
  appendixes?: boolean;
}

export interface ProposalCardProps {
  kind: 'trade' | 'policy change' | 'thesis revision';
  principal?: Principal;
  actor?: string;
  reason?: string;
  evidence?: EvidenceItem[];
  /** The exact change as the server will apply it. Shown, never summarised. */
  payload?: Record<string, unknown> | Array<[string, unknown]>;
  targetRevision?: string;
  at?: string;
  state?: 'pending' | 'stale' | 'confirmed' | 'rejected';
  /** On `stale`: the revision the target moved to. A new proposal is needed. */
  currentRevision?: string;
  by?: string;
  /** On `confirmed`: the resulting record. */
  record?: string;
  /** On `rejected`: the Owner's reason. */
  rejectionReason?: string;
  onConfirm?: () => void;
  onReject?: () => void;
}

export interface ConfirmDialogProps {
  title?: string;
  payload?: Record<string, unknown> | Array<[string, unknown]>;
  targetRevision?: string;
  /** `stale` disables the confirm rather than closing the dialog. */
  state?: 'open' | 'stale' | 'confirming' | 'done';
  onConfirm?: () => void;
  onReject?: () => void;
  onCancel?: () => void;
  onReload?: () => void;
}

export interface ScreenRow {
  ticker: string;
  name: string;
  /** fairband: `null` when the engine could not classify the company. */
  phase: Phase | null;
  fairLow: number;
  fairHigh: number;
  fairValue?: number;
  /** fairband: `null` on a refusal. */
  buyLevel?: number | null;
  trimLevel?: number | null;
  price: number;
  /** Computed from the system's own inputs only. */
  mechanical: number;
  /** Computed with the overrides inside. `null` when there are none. */
  reviewed: number | null;
  /** How many overrides are inside the reviewed value. */
  overrides?: number;
  /** fairband: an ISO timestamp; the Entered cell shows its date, the full ISO in `datetime`. */
  enteredAt?: string;
  freshness?: Freshness;
  selected?: boolean;
  /** Derived, like every value: price x shares at the last run. */
  cap?: CapSize;
  /** One of SECTORS. A fact about the company, not a judgement. fairband: `null` when unknown. */
  sector?: string | null;
  /**
   * fairband: the extra columns (spec 6.3). Fractions (`impliedGrowth`, `expectedReturn`, the
   * changes, `drawdown`) render as percentages; dates are ISO. `null` renders an em dash.
   */
  capBand?: string | null;
  marketCap?: number | null;
  moat?: string | null;
  impliedGrowth?: number | null;
  expectedReturn?: number | null;
  epv?: number | null;
  peReported?: number | null;
  peClean?: number | null;
  peForward?: number | null;
  high52w?: number | null;
  low52w?: number | null;
  change1y?: number | null;
  change3y?: number | null;
  change5y?: number | null;
  drawdown?: number | null;
  /** The flags' short words, joined by ` · `. */
  flags?: string[];
  /** The refusal reason; `null` when the engine gave a value, and the cell is then empty. */
  refusal?: string | null;
  priceDate?: string | null;
  dataDate?: string;
  validUntil?: string;
  /**
   * fairband: a growth row's target margin and the margin its price needs, fractions rendered as
   * percentages; a row refused for its target margin has `impliedMargin` alone.
   */
  targetMargin?: number | null;
  impliedMargin?: number | null;
  /**
   * fairband: price ÷ value and its word; `null` on a refusal, a placeholder and a snapshot valued
   * before the designation, and the Price vs value cell then shows an em dash.
   */
  priceToValue?: number | null;
  designation?: Designation | null;
  /** Rows may carry anything else the caller filters or sorts on; the
      component reads only the fields above. */
  [key: string]: unknown;
}

/** The four buckets above the universe's size floor. */
export type CapSize = 'mega' | 'large' | 'mid' | 'small';

/**
 * What the Filters menu holds. Empty arrays and false flags mean no narrowing;
 * a non-empty array is a whitelist. The component never applies any of it —
 * it reports changes and the caller filters `rows`.
 */
export interface ScreenFilters {
  /** fairband: the price-vs-value words; a row without one matches none. */
  designation: Designation[];
  phase: Phase[];
  cap: CapSize[];
  /** Sector names, as they appear in SECTORS. */
  sector: string[];
  /** Hide companies whose reviewed value is null. */
  reviewedOnly: boolean;
  /** Hide companies whose value is past its validity window. */
  hideExpired: boolean;
}

export interface ScreenTableProps {
  /** Already filtered and sorted. The component does neither. */
  rows: ScreenRow[];
  /**
   * Visible column keys. Defaults to DEFAULT_COLUMNS; ticker and price always show.
   * fairband: ordered; the table renders in this order and a header drop calls `onColumnsChange`
   * with the new order. Given `onColumnsChange`, each header cell is draggable; the dragged
   * column takes the target's index. A locked column the list leaves out still shows, ticker
   * first and price last; unknown keys are left out. The chooser lists the columns in this
   * order, then the rest in catalog order.
   */
  columns?: string[];
  /** Makes the chooser live. Without it the chooser renders inert. */
  onColumnsChange?: (columns: string[]) => void;
  /** `false` hides the bar with the footnote and the chooser. */
  chooser?: boolean;
  dense?: boolean;
  /** For the header indicator only; sorting happens in the engine. */
  sort?: { column: string; direction: 'asc' | 'desc' };
  /**
   * fairband: called with a column key when its header is clicked, or focused and given Enter or
   * Space. The consumer asks the engine for the new order; the component sorts nothing. Without
   * it the headers are inert. Each header cell carries its key in `data-key`.
   */
  onSort?: (column: string) => void;
  /**
   * fairband: called with the row when it is clicked, or focused and given Enter or Space. Given
   * it, each row takes `tabindex="0"` and stays a native row; without it the rows are inert. A
   * row with `selected` carries `aria-current="true"`.
   */
  onOpen?: (row: ScreenRow) => void;
  /** Free text, shown in the FIND field. Supplying `onQueryChange` is what
      makes the field appear at all. */
  query?: string;
  onQueryChange?: (query: string) => void;
  /** Current filter state. Supplying `onFiltersChange` is what makes the
      Filters menu appear. */
  filters?: ScreenFilters;
  onFiltersChange?: (filters: ScreenFilters) => void;
  /** Overrides the eleven GICS sectors in the menu. There is rarely a reason. */
  sectors?: string[];
  /** Size of the unfiltered universe. With it the bar says `41 of 4,112`
      and offers Clear; without it the bar falls back to `footnote`. */
  total?: number;
  /** Free text for the count slot. Ignored when `total` is given. */
  footnote?: string;
}

/* ---------------------------------------------------------------- charts */

export interface BandPoint {
  period: string;
  price: number;
  fairLow: number;
  fairHigh: number;
  freshness?: Freshness;
}

export interface BandHistoryProps {
  series: BandPoint[];
  title?: string;
  subtitle?: string;
  basis?: Basis;
  height?: number;
  width?: number;
  tableView?: boolean;
}

export interface BarPoint {
  period: string;
  value: number;
  freshness?: Freshness;
}

export interface HistoryBarsProps {
  /** One measure per chart. Two measures are two charts, never two y-axes. */
  series: BarPoint[];
  title: string;
  unit?: string;
  format?: (value: number) => string;
  basis?: Basis;
  height?: number;
  width?: number;
  tableView?: boolean;
}

export interface SpreadPoint {
  period: string;
  roic: number;
  wacc: number;
  freshness?: Freshness;
}

export interface SpreadChartProps {
  series: SpreadPoint[];
  title?: string;
  subtitle?: string;
  basis?: Basis;
  height?: number;
  width?: number;
  tableView?: boolean;
}

export interface SensitivityGridProps {
  rows: string[];
  cols: string[];
  /** cells[row][col] = value per share at that pair of assumptions. */
  cells: number[][];
  /** Today's price. Cells are coloured by distance from this, not by magnitude. */
  price: number;
  current?: { row: number; col: number };
  rowLabel?: string;
  colLabel?: string;
  basis?: Basis;
  title?: string;
  subtitle?: string;
}

export declare function AppHeader(props: AppHeaderProps): unknown;
export declare function Mark(props: MarkProps): unknown;
export declare function RunProgress(props: RunProgressProps): unknown;
export declare function Button(props: ButtonProps): unknown;
export declare function PhaseBadge(props: PhaseBadgeProps): unknown;
export declare function PrincipalChip(props: PrincipalChipProps): unknown;
export declare function BasisChip(props: BasisChipProps): unknown;
export declare function ValueCell(props: ValueCellProps): unknown;
export declare function ValueBridge(props: ValueBridgeProps): unknown;
export declare function BandMeter(props: BandMeterProps): unknown;
export declare function ValidityWindow(props: ValidityWindowProps): unknown;
export declare function TaggedInput(props: TaggedInputProps): unknown;
export declare function OverrideRecord(props: OverrideRecordProps): unknown;
export declare function ReportReader(props: ReportReaderProps): unknown;
export declare function ProposalCard(props: ProposalCardProps): unknown;
export declare function ConfirmDialog(props: ConfirmDialogProps): unknown;
export declare function ScreenTable(props: ScreenTableProps): unknown;
export declare function BandHistory(props: BandHistoryProps): unknown;
export declare function HistoryBars(props: HistoryBarsProps): unknown;
export declare function SpreadChart(props: SpreadChartProps): unknown;
export declare function SensitivityGrid(props: SensitivityGridProps): unknown;

/** Phase number to Damodaran's name for it. */
export declare const PHASES: Record<Phase, string>;
/** fairband: the five words by code, in band order. */
export declare const DESIGNATION: Record<Designation, string>;
/** The screen's default eight columns. */
export declare const DEFAULT_COLUMNS: string[];
/** fairband: every column's key, in catalog order. */
export declare const COLUMN_KEYS: string[];
/** The four cap buckets, each with its word and the range it covers. */
export declare const CAPS: { id: CapSize; word: string; note: string }[];
/** The eleven GICS sectors, in GICS order. */
export declare const SECTORS: string[];
/** A ScreenFilters with nothing narrowed. Use it as the initial state. */
export declare const EMPTY_FILTERS: ScreenFilters;
/** ISO in, `3 Dec 2026` out — or `3 Dec 2026, 09:40` when the string carries a time. */
export declare function formatDate(iso: string): string;
/** Number in, `$121.30` out. */
export declare function formatMoney(value: number): string;
/** fairband: a fraction in, `4.4%` out: one decimal, U+2212 for a minus, an em dash for null. */
export declare function formatPercent(value: number | null): string;
