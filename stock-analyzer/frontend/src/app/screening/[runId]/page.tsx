"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import StockCard, { type StockResult } from "@/components/stock-card";
import StockListRow from "@/components/StockListRow";
import StockDetailModal from "@/components/StockDetailModal";
import ViewToggle from "@/components/ViewToggle";
import BulkActions from "@/components/bulk-actions";
import PipelineStatus from "@/components/pipeline-status";
import ProgressPanel from "@/components/ProgressPanel";
import { SkeletonCard } from "@/components/Skeleton";
import { useTaskContext, type ProgressData } from "@/contexts/TaskContext";
import { METRIC_LABELS } from "@/components/metric-config";

interface TaskStatus {
	id: number;
	task_type: string;
	status: string;
	progress: string | null;
	progress_data: ProgressData | null;
	result_id: number | null;
	error_message: string | null;
	created_at: string | null;
}

interface ResultsPage {
	results: StockResult[];
	total: number;
}

interface RunDetails {
	id: number;
	created_at: string;
	filter_config: Record<string, { min?: number; max?: number }> | null;
}

const SORT_OPTIONS = [
	{ value: "composite_score", label: "Composite Score" },
	{ value: "stock_ticker", label: "Ticker" },
];

const METRIC_SORT_OPTIONS = [
	{ value: "pe_ratio", label: "P/E Ratio" },
	{ value: "roe", label: "ROE" },
	{ value: "roa", label: "ROA" },
	{ value: "debt_to_equity", label: "Debt/Equity" },
	{ value: "current_ratio", label: "Current Ratio" },
	{ value: "gross_margin", label: "Gross Margin" },
	{ value: "net_profit_margin", label: "Net Margin" },
	{ value: "dividend_yield", label: "Dividend Yield" },
	{ value: "pb_ratio", label: "P/B Ratio" },
	{ value: "ps_ratio", label: "P/S Ratio" },
	{ value: "peg_ratio", label: "PEG Ratio" },
	{ value: "price_to_fcf", label: "Price/FCF" },
];

export default function ScreeningResultsPage() {
	const params = useParams<{ runId: string }>();
	const rawRunId = params.runId;

	// Support navigation from "task-{taskId}" or direct "{runId}"
	const isTaskBased = rawRunId.startsWith("task-");
	const taskIdFromUrl = isTaskBased
		? parseInt(rawRunId.replace("task-", ""), 10)
		: null;

	const [runId, setRunId] = useState<number | null>(
		isTaskBased ? null : parseInt(rawRunId, 10),
	);
	const [taskId] = useState<number | null>(taskIdFromUrl);
	const [taskStatus, setTaskStatus] = useState<string>("pending");
	const [taskProgress, setTaskProgress] = useState<string | null>(null);
	const [taskProgressData, setTaskProgressData] = useState<ProgressData | null>(null);
	const [taskCreatedAt, setTaskCreatedAt] = useState<string | null>(null);
	const [taskError, setTaskError] = useState<string | null>(null);
	const [cancelling, setCancelling] = useState(false);

	const { registerTask } = useTaskContext();

	const [view, setView] = useState<"grid" | "list">(() => {
		if (typeof window === "undefined") return "grid";
		const stored = localStorage.getItem("screening-results-view");
		return stored === "list" ? "list" : "grid";
	});
	const [selectedStock, setSelectedStock] = useState<StockResult | null>(null);
	const [runDetails, setRunDetails] = useState<RunDetails | null>(null);

	const [results, setResults] = useState<StockResult[]>([]);
	const [total, setTotal] = useState(0);
	const [loading, setLoading] = useState(true);

	const [sortBy, setSortBy] = useState("composite_score");
	const [order, setOrder] = useState<"asc" | "desc">("desc");
	const [sectorFilter, setSectorFilter] = useState("");
	const [minScore, setMinScore] = useState(0);
	const [maxScore, setMaxScore] = useState(100);

	const [selected, setSelected] = useState<Set<number>>(new Set());
	const [tickerSearch, setTickerSearch] = useState("");
	const [showRejected, setShowRejected] = useState(false);
	const [showAdvanced, setShowAdvanced] = useState(false);
	const [researchStatus, setResearchStatus] = useState<
		Record<number, "loading" | "started" | "failed">
	>({});

	const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

	// -----------------------------------------------------------------------
	// Poll task status (when navigated via task-{id})
	// -----------------------------------------------------------------------
	const pollTask = useCallback(async () => {
		if (taskId === null) return;
		try {
			const data = await apiFetch<TaskStatus>(`/screening/tasks/${taskId}/status`);
			setTaskStatus(data.status);
			setTaskProgress(data.progress);
			setTaskProgressData(data.progress_data);
			if (data.created_at) setTaskCreatedAt(data.created_at);
			if (data.error_message) setTaskError(data.error_message);

			if ((data.status === "completed" || data.status === "cancelled") && data.result_id) {
				setRunId(data.result_id);
				if (pollingRef.current) {
					clearInterval(pollingRef.current);
					pollingRef.current = null;
				}
			} else if (data.status === "failed") {
				if (pollingRef.current) {
					clearInterval(pollingRef.current);
					pollingRef.current = null;
				}
				setLoading(false);
			}
		} catch {
			// Ignore transient errors during polling
		}
	}, [taskId]);

	useEffect(() => {
		if (taskId !== null) {
			registerTask(taskId);
		}
	}, [taskId, registerTask]);

	useEffect(() => {
		if (taskId !== null && runId === null) {
			pollTask();
			pollingRef.current = setInterval(pollTask, 3000);
			return () => {
				if (pollingRef.current) clearInterval(pollingRef.current);
			};
		}
	}, [taskId, runId, pollTask]);

	// -----------------------------------------------------------------------
	// Fetch results once we have a runId
	// -----------------------------------------------------------------------
	const fetchResults = useCallback(async () => {
		if (runId === null) return;
		setLoading(true);
		try {
			const qs = new URLSearchParams({
				sort_by: sortBy,
				order,
				limit: "200",
				offset: "0",
			}).toString();
			const data = await apiFetch<ResultsPage>(`/screening/${runId}?${qs}`);
			setResults(data.results);
			setTotal(data.total);
		} catch {
			setTaskError("Failed to load results");
		} finally {
			setLoading(false);
		}
	}, [runId, sortBy, order]);

	useEffect(() => {
		fetchResults();
	}, [fetchResults]);

	// Fetch run details (settings)
	useEffect(() => {
		if (runId === null) return;
		apiFetch<RunDetails>(`/screening/runs/${runId}`)
			.then(setRunDetails)
			.catch(() => {
				// Non-critical — settings header just won't show
			});
	}, [runId]);

	// Auto-refresh while any stocks are in "researching" state
	const hasResearching = results.some((r) => r.stage === "researching");
	const researchPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

	useEffect(() => {
		if (hasResearching && !researchPollRef.current) {
			researchPollRef.current = setInterval(fetchResults, 5000);
		}
		if (!hasResearching && researchPollRef.current) {
			clearInterval(researchPollRef.current);
			researchPollRef.current = null;
		}
		return () => {
			if (researchPollRef.current) {
				clearInterval(researchPollRef.current);
				researchPollRef.current = null;
			}
		};
	}, [hasResearching, fetchResults]);

	// -----------------------------------------------------------------------
	// Derived data
	// -----------------------------------------------------------------------
	const sectors = Array.from(
		new Set(
			results
				.map((r) => (r.metric_snapshot?.sector as unknown as string) || "")
				.filter(Boolean),
		),
	).sort();

	const isMetricSort = METRIC_SORT_OPTIONS.some((o) => o.value === sortBy);

	const filteredResults = results
		.filter((r) => {
			if (!showRejected && r.stage === "rejected") return false;
			if (
				sectorFilter &&
				(r.metric_snapshot?.sector as unknown as string) !== sectorFilter
			)
				return false;
			if (r.composite_score < minScore || r.composite_score > maxScore)
				return false;
			if (tickerSearch && !r.stock_ticker.toLowerCase().includes(tickerSearch.toLowerCase()))
				return false;
			return true;
		})
		.sort((a, b) => {
			if (!isMetricSort) return 0;
			const aVal = (a.metric_snapshot?.[sortBy] as number) ?? null;
			const bVal = (b.metric_snapshot?.[sortBy] as number) ?? null;
			if (aVal === null && bVal === null) return 0;
			if (aVal === null) return 1;
			if (bVal === null) return -1;
			return order === "asc" ? aVal - bVal : bVal - aVal;
		});

	const stageCounts = {
		screened: results.filter((r) => r.stage === "screened").length,
		researching: results.filter((r) => r.stage === "researching").length,
		researched: results.filter((r) => r.stage === "researched").length,
		rejected: results.filter((r) => r.stage === "rejected").length,
	};

	// -----------------------------------------------------------------------
	// Selection
	// -----------------------------------------------------------------------
	function toggleSelection(id: number) {
		setSelected((prev) => {
			const next = new Set(prev);
			if (next.has(id)) {
				next.delete(id);
			} else {
				next.add(id);
			}
			return next;
		});
	}

	function toggleSelectAll() {
		const visibleIds = filteredResults.map((r) => r.id);
		const allSelected = visibleIds.every((id) => selected.has(id));
		if (allSelected) {
			setSelected(new Set());
		} else {
			setSelected(new Set(visibleIds));
		}
	}

	// -----------------------------------------------------------------------
	// Bulk actions
	// -----------------------------------------------------------------------
	async function updateStage(resultId: number, stage: string) {
		if (runId === null) return;
		try {
			const updated = await apiFetch<StockResult>(`/screening/${runId}`, {
				method: "PATCH",
				body: JSON.stringify({ resultId, stage }),
			});
			setResults((prev) => prev.map((r) => (r.id === resultId ? updated : r)));
		} catch {
			// Revert on failure — refetch
			fetchResults();
		}
	}

	async function triggerResearch(ids: number[]) {
		const stocks = results.filter((r) => ids.includes(r.id));
		const tickers = stocks.map((r) => r.stock_ticker);
		if (tickers.length === 0) return;

		// Mark loading
		setResearchStatus((prev) => {
			const next = { ...prev };
			for (const id of ids) next[id] = "loading";
			return next;
		});

		// Persist stage changes
		setResults((prev) =>
			prev.map((r) =>
				ids.includes(r.id) ? { ...r, stage: "researching" } : r,
			),
		);
		for (const id of ids) {
			await updateStage(id, "researching");
		}

		// Trigger research
		try {
			await apiFetch("/research", {
				method: "POST",
				body: JSON.stringify({ stock_tickers: tickers }),
			});
			setResearchStatus((prev) => {
				const next = { ...prev };
				for (const id of ids) next[id] = "started";
				return next;
			});
		} catch {
			setResearchStatus((prev) => {
				const next = { ...prev };
				for (const id of ids) next[id] = "failed";
				return next;
			});
		}
	}

	async function bulkResearch() {
		const ids = Array.from(selected);
		setSelected(new Set());
		await triggerResearch(ids);
	}

	async function bulkReject() {
		const ids = Array.from(selected);
		setResults((prev) =>
			prev.map((r) => (ids.includes(r.id) ? { ...r, stage: "rejected" } : r)),
		);
		setSelected(new Set());
		for (const id of ids) {
			await updateStage(id, "rejected");
		}
	}

	async function unreject(resultId: number) {
		await updateStage(resultId, "screened");
	}

	async function retryResearch(stock: StockResult) {
		await triggerResearch([stock.id]);
	}

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	async function handleCancel() {
		if (taskId === null) return;
		setCancelling(true);
		try {
			await apiFetch(`/screening/tasks/${taskId}/cancel`, { method: "POST" });
		} catch {
			setCancelling(false);
		}
	}

	// Task is still running
	if (taskId !== null && runId === null) {
		return (
			<div className="mx-auto max-w-lg py-12">
				{taskStatus === "failed" ? (
					<div className="text-center">
						<p className="text-sm font-medium text-red-600">Screening failed</p>
						{taskError && (
							<p className="mt-1 text-xs text-red-500">{taskError}</p>
						)}
						<a
							href="/screening"
							className="mt-4 inline-block text-sm text-blue-600 hover:underline"
						>
							Back to screening
						</a>
					</div>
				) : (
					<>
						<ProgressPanel
							status={taskStatus}
							progress={taskProgress}
							progressData={taskProgressData}
							createdAt={taskCreatedAt}
							errorMessage={taskError}
						/>
						{(taskStatus === "running" || taskStatus === "pending") && (
							<div className="mt-4 text-center">
								<button
									onClick={handleCancel}
									disabled={cancelling}
									className="rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 disabled:opacity-50"
								>
									{cancelling ? "Cancelling, saving results..." : "Cancel Screen"}
								</button>
							</div>
						)}
					</>
				)}
			</div>
		);
	}

	if (loading) {
		return (
			<div className="grid grid-cols-1 gap-4 pt-12 md:grid-cols-2">
				<SkeletonCard />
				<SkeletonCard />
				<SkeletonCard />
				<SkeletonCard />
			</div>
		);
	}

	if (taskError && results.length === 0) {
		return (
			<div className="flex flex-col items-center justify-center py-20">
				<p className="text-sm text-red-600">{taskError}</p>
				<a
					href="/screening"
					className="mt-4 text-sm text-blue-600 hover:underline"
				>
					Back to screening
				</a>
			</div>
		);
	}

	const allVisibleSelected =
		filteredResults.length > 0 &&
		filteredResults.every((r) => selected.has(r.id));

	return (
		<div className="pb-20">
			{/* Header */}
			<div className="mb-6">
				<div className="flex items-center gap-3">
					<a
						href="/screening"
						className="text-sm text-gray-400 hover:text-gray-600"
					>
						Screening
					</a>
					<span className="text-sm text-gray-300">/</span>
					<h1 className="text-2xl font-bold text-gray-900">Run #{runId}</h1>
					<span className="text-sm text-gray-500">{total} results</span>
				</div>
			</div>

			{/* Run settings header */}
			{runDetails?.filter_config && Object.keys(runDetails.filter_config).length > 0 && (
				<div className="mb-6 rounded-xl border border-gray-200 bg-white px-5 py-3">
					<p className="mb-2 text-xs font-medium text-gray-500">Thresholds used for this run</p>
					<div className="flex flex-wrap gap-2">
						{Object.entries(runDetails.filter_config).map(([key, cfg]) => {
							const label = METRIC_LABELS[key] || key.replace(/_/g, " ");
							const parts: string[] = [];
							if (cfg.min != null) parts.push(`min ${cfg.min}`);
							if (cfg.max != null) parts.push(`max ${cfg.max}`);
							return (
								<span
									key={key}
									className="inline-flex items-center gap-1 rounded-md bg-gray-50 px-2 py-1 text-xs text-gray-600"
								>
									<span className="font-medium">{label}:</span>
									{parts.join(", ")}
								</span>
							);
						})}
					</div>
				</div>
			)}

			{/* Pipeline status */}
			<div className="mb-6">
				<PipelineStatus {...stageCounts} />
			</div>

			{/* Controls */}
			<div className="mb-6 rounded-xl border border-gray-200 bg-white">
				<div className="flex flex-wrap items-center gap-4 px-5 py-3">
					{/* Ticker search */}
					<input
						type="text"
						placeholder="Search ticker..."
						value={tickerSearch}
						onChange={(e) => setTickerSearch(e.target.value)}
						className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-900 placeholder-gray-400 focus:border-gray-400 focus:outline-none"
					/>

					{/* Sort */}
					<div className="flex items-center gap-2">
						<label
							htmlFor="sort-by"
							className="text-xs font-medium text-gray-500"
						>
							Sort by
						</label>
						<select
							id="sort-by"
							value={sortBy}
							onChange={(e) => setSortBy(e.target.value)}
							className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700"
						>
							{SORT_OPTIONS.map((opt) => (
								<option key={opt.value} value={opt.value}>
									{opt.label}
								</option>
							))}
						</select>
						<button
							onClick={() => setOrder((o) => (o === "asc" ? "desc" : "asc"))}
							className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
							aria-label={`Sort ${order === "asc" ? "ascending" : "descending"}`}
						>
							{order === "asc" ? "↑ Asc" : "↓ Desc"}
						</button>
					</div>

					{/* Advanced toggle */}
					<button
						onClick={() => setShowAdvanced((v) => !v)}
						className={`flex items-center gap-1 rounded-lg border px-3 py-1.5 text-sm transition-colors ${
							showAdvanced
								? "border-blue-200 bg-blue-50 text-blue-700"
								: "border-gray-200 text-gray-500 hover:text-gray-700"
						}`}
					>
						<svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
						</svg>
						Advanced
					</button>

					{/* View toggle / Select all / Show rejected */}
					<div className="ml-auto flex items-center gap-4">
						<ViewToggle storageKey="screening-results-view" onChange={setView} />
						<label className="flex items-center gap-2 text-sm text-gray-600">
							<input
								type="checkbox"
								checked={showRejected}
								onChange={() => setShowRejected((v) => !v)}
								className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
							/>
							Show rejected
						</label>
						<button
							onClick={toggleSelectAll}
							className="text-sm font-medium text-blue-600 hover:text-blue-700"
						>
						{allVisibleSelected ? "Deselect all" : "Select all"}
					</button>
				</div>
				</div>

				{/* Advanced filters */}
				{showAdvanced && (
					<div className="border-t border-gray-100 px-5 py-3">
						<div className="flex flex-wrap items-center gap-4">
							{/* Sort by metric */}
							<div className="flex items-center gap-2">
								<label htmlFor="metric-sort" className="text-xs font-medium text-gray-500">
									Sort by metric
								</label>
								<select
									id="metric-sort"
									value={isMetricSort ? sortBy : ""}
									onChange={(e) => {
										if (e.target.value) {
											setSortBy(e.target.value);
										} else {
											setSortBy("composite_score");
										}
									}}
									className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700"
								>
									<option value="">None</option>
									{METRIC_SORT_OPTIONS.map((opt) => (
										<option key={opt.value} value={opt.value}>
											{opt.label}
										</option>
									))}
								</select>
							</div>

							{/* Sector filter */}
							<div className="flex items-center gap-2">
								<label htmlFor="sector-filter" className="text-xs font-medium text-gray-500">
									Sector
								</label>
								<select
									id="sector-filter"
									value={sectorFilter}
									onChange={(e) => setSectorFilter(e.target.value)}
									className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700"
								>
									<option value="">All sectors</option>
									{sectors.map((s) => (
										<option key={s} value={s}>
											{s}
										</option>
									))}
								</select>
							</div>

							{/* Score range */}
							<div className="flex items-center gap-2">
								<label className="text-xs font-medium text-gray-500">Score</label>
								<input
									type="number"
									min={0}
									max={100}
									value={minScore}
									onChange={(e) => setMinScore(Number(e.target.value))}
									className="w-16 rounded-lg border border-gray-200 px-2 py-1.5 text-sm tabular-nums text-gray-700"
									aria-label="Minimum score"
								/>
								<span className="text-xs text-gray-400">to</span>
								<input
									type="number"
									min={0}
									max={100}
									value={maxScore}
									onChange={(e) => setMaxScore(Number(e.target.value))}
									className="w-16 rounded-lg border border-gray-200 px-2 py-1.5 text-sm tabular-nums text-gray-700"
									aria-label="Maximum score"
								/>
							</div>
						</div>
					</div>
				)}
			</div>

			{/* Results */}
			{filteredResults.length === 0 ? (
				<div className="rounded-xl border border-gray-200 bg-white py-16 text-center">
					<p className="text-sm text-gray-500">
						No results match your filters.
					</p>
				</div>
			) : view === "list" ? (
				<div className="rounded-xl border border-gray-200 bg-white">
					{filteredResults.map((stock) => (
						<StockListRow
							key={stock.id}
							stock={stock}
							onClick={() => setSelectedStock(stock)}
						/>
					))}
				</div>
			) : (
				<div className="grid grid-cols-1 gap-4 md:grid-cols-2">
					{filteredResults.map((stock) => (
						<StockCard
							key={stock.id}
							stock={stock}
							selected={selected.has(stock.id)}
							onToggle={toggleSelection}
							action={
								<>
									{stock.stage === "rejected" && showRejected && (
										<button
											onClick={() => unreject(stock.id)}
											className="rounded-lg border border-gray-200 px-2.5 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50"
										>
											Un-reject
										</button>
									)}
									{stock.stage === "researching" &&
										(() => {
											const status = researchStatus[stock.id];
											if (status === "loading") {
												return (
													<span className="inline-flex items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-600">
														<span className="h-3 w-3 animate-spin rounded-full border-2 border-blue-200 border-t-blue-600" />
														Starting research...
													</span>
												);
											}
											if (status === "started") {
												return (
													<span className="inline-flex items-center gap-1.5 rounded-lg border border-green-200 bg-green-50 px-2.5 py-1 text-xs font-medium text-green-600">
														Research started - view progress on Research page
													</span>
												);
											}
											if (status === "failed") {
												return (
													<div className="flex items-center gap-2">
														<span className="text-xs font-medium text-red-600">
															Failed to start
														</span>
														<button
															onClick={() => retryResearch(stock)}
															className="rounded-lg border border-red-200 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
														>
															Try Again
														</button>
													</div>
												);
											}
											return (
												<button
													onClick={() => retryResearch(stock)}
													className="rounded-lg border border-blue-200 px-2.5 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50"
												>
													Retry Research
												</button>
											);
										})()}
									{stock.stage === "researched" && (
										<a
											href={`/research/${stock.stock_ticker}`}
											className="inline-flex items-center gap-1.5 rounded-lg border border-green-200 px-2.5 py-1 text-xs font-medium text-green-700 hover:bg-green-50"
										>
											Research complete: View report
										</a>
									)}
								</>
							}
						/>
					))}
				</div>
			)}

			{/* Stock detail modal (list view) */}
			{selectedStock && (
				<StockDetailModal
					stock={selectedStock}
					onClose={() => setSelectedStock(null)}
				/>
			)}

			{/* Floating bulk action bar */}
			<BulkActions
				selectedCount={selected.size}
				onResearch={bulkResearch}
				onReject={bulkReject}
			/>
		</div>
	);
}
