"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import StockCard, { type StockResult } from "@/components/stock-card";
import BulkActions from "@/components/bulk-actions";
import PipelineStatus from "@/components/pipeline-status";

interface TaskStatus {
	id: number;
	task_type: string;
	status: string;
	progress: string | null;
	result_id: number | null;
	error_message: string | null;
}

interface ResultsPage {
	results: StockResult[];
	total: number;
}

const SORT_OPTIONS = [
	{ value: "composite_score", label: "Composite Score" },
	{ value: "stock_ticker", label: "Ticker" },
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
	const [taskError, setTaskError] = useState<string | null>(null);

	const [results, setResults] = useState<StockResult[]>([]);
	const [total, setTotal] = useState(0);
	const [loading, setLoading] = useState(true);

	const [sortBy, setSortBy] = useState("composite_score");
	const [order, setOrder] = useState<"asc" | "desc">("desc");
	const [sectorFilter, setSectorFilter] = useState("");
	const [minScore, setMinScore] = useState(0);
	const [maxScore, setMaxScore] = useState(100);

	const [selected, setSelected] = useState<Set<number>>(new Set());
	const [showRejected, setShowRejected] = useState(false);
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
			const data = await apiFetch<TaskStatus>(`/tasks/${taskId}`);
			setTaskStatus(data.status);
			setTaskProgress(data.progress);
			if (data.error_message) setTaskError(data.error_message);

			if (data.status === "completed" && data.result_id) {
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

	const filteredResults = results.filter((r) => {
		if (!showRejected && r.stage === "rejected") return false;
		if (
			sectorFilter &&
			(r.metric_snapshot?.sector as unknown as string) !== sectorFilter
		)
			return false;
		if (r.composite_score < minScore || r.composite_score > maxScore)
			return false;
		return true;
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

	// Task is still running
	if (taskId !== null && runId === null) {
		return (
			<div className="flex flex-col items-center justify-center py-20">
				{taskStatus === "failed" ? (
					<>
						<p className="text-sm font-medium text-red-600">Screening failed</p>
						{taskError && (
							<p className="mt-1 text-xs text-red-500">{taskError}</p>
						)}
						<a
							href="/screening"
							className="mt-4 text-sm text-blue-600 hover:underline"
						>
							Back to screening
						</a>
					</>
				) : (
					<>
						<div className="mb-4 h-8 w-8 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" />
						<p className="text-sm font-medium text-gray-700">
							Running screen...
						</p>
						{taskProgress && (
							<p className="mt-1 text-xs text-gray-500">{taskProgress}</p>
						)}
					</>
				)}
			</div>
		);
	}

	if (loading) {
		return (
			<div className="flex items-center justify-center py-20">
				<div className="text-sm text-gray-500">Loading results...</div>
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

			{/* Pipeline status */}
			<div className="mb-6">
				<PipelineStatus {...stageCounts} />
			</div>

			{/* Controls */}
			<div className="mb-6 flex flex-wrap items-center gap-4 rounded-xl border border-gray-200 bg-white px-5 py-3">
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

				{/* Sector filter */}
				<div className="flex items-center gap-2">
					<label
						htmlFor="sector-filter"
						className="text-xs font-medium text-gray-500"
					>
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

				{/* Select all / Show rejected */}
				<div className="ml-auto flex items-center gap-4">
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

			{/* Results grid */}
			{filteredResults.length === 0 ? (
				<div className="rounded-xl border border-gray-200 bg-white py-16 text-center">
					<p className="text-sm text-gray-500">
						No results match your filters.
					</p>
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

			{/* Floating bulk action bar */}
			<BulkActions
				selectedCount={selected.size}
				onResearch={bulkResearch}
				onReject={bulkReject}
			/>
		</div>
	);
}
