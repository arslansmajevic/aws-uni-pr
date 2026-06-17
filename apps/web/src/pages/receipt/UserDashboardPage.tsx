// apps/web/src/pages/receipt/UserDashboardPage.tsx
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getReceipts, deleteReceipt } from '../../services/receipts'

export function UserDashboardPage() {
	const [receipts, setReceipts] = useState<any[]>([])
	const [isLoading, setIsLoading] = useState(true)
	const [errorMessage, setErrorMessage] = useState<string | null>(null)
	const [copiedId, setCopiedId] = useState<string | null>(null)
	const [isBankConnected, setIsBankConnected] = useState(false)

	useEffect(() => {
		loadData()
		setIsBankConnected(localStorage.getItem('isBankConnected') === 'true')
	}, [])

	useEffect(() => {
		const hasProcessingReceipts = receipts.some(r => r.processingStatus === 'PROCESSING')
		if (!hasProcessingReceipts) {
			return
		}

		// Poll every 3 seconds while at least one receipt is still being
		// processed, so the status updates automatically without the user
		// needing to manually refresh the page.
		const intervalId = window.setInterval(() => {
			loadData({ silent: true })
		}, 3000)

		return () => window.clearInterval(intervalId)
	}, [receipts])

	async function loadData(options: { silent?: boolean } = {}) {
		try {
			if (!options.silent) {
				setIsLoading(true)
			}
			setErrorMessage(null)
			const dbReceipts = await getReceipts()
			setReceipts(dbReceipts)
		} catch (err) {
			if (!options.silent) {
				setErrorMessage('Failed to load receipts from live AWS database.')
			}
		} finally {
			if (!options.silent) {
				setIsLoading(false)
			}
		}
	}

	async function handleDelete(receiptId: string) {
		if (!window.confirm('Are you sure you want to delete this receipt?')) return
		try {
			await deleteReceipt(receiptId)
			setReceipts(prev => prev.filter(r => r.receiptId !== receiptId))
		} catch (err) {
			alert(err instanceof Error ? err.message : 'Failed to delete receipt.')
		}
	}

	async function handleCopyId(id: string) {
		try {
			await navigator.clipboard.writeText(id)
			setCopiedId(id)
			window.setTimeout(() => setCopiedId(current => current === id ? null : current), 1500)
		} catch {
			setCopiedId(null)
		}
	}

	function getMonthLabel(dateStr: string | undefined | null): string {
		if (!dateStr) return 'Processing & Unsorted'
		try {
			const dateObj = new Date(dateStr)
			if (isNaN(dateObj.getTime())) return 'Processing & Unsorted'
			return dateObj.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })
		} catch {
			return 'Processing & Unsorted'
		}
	}

	function parseAmount(value: any): number {
		if (!value) return 0
		try {
			const cleaned = String(value)
				.replace(',', '.')
				.replace('CHF', '')
				.replace('$', '')
				.replace('€', '')
				.trim()
			const parsed = parseFloat(cleaned)
			return isNaN(parsed) ? 0 : parsed
		} catch {
			return 0
		}
	}

	const sortedReceipts = [...receipts].sort((a, b) => {
		const dateA = a.receiptDate || ''
		const dateB = b.receiptDate || ''
		return dateB.localeCompare(dateA)
	})

	const groupedMonths: { month: string; items: any[] }[] = []
	sortedReceipts.forEach(receipt => {
		const label = getMonthLabel(receipt.receiptDate)
		let existingGroup = groupedMonths.find(g => g.month === label)
		if (!existingGroup) {
			existingGroup = { month: label, items: [] }
			groupedMonths.push(existingGroup)
		}
		existingGroup.items.push(receipt)
	})

	const validCategories = ["Groceries", "Dining", "Entertainment", "Transport", "Health", "Shopping", "Utilities", "Other"]
	const categoryBreakdown = validCategories.reduce((acc, cat) => {
		acc[cat] = { count: 0, totalSpend: 0 }
		return acc;
	}, {} as Record<string, { count: number; totalSpend: number }>)

	let calculatedTotalSpend = 0
	receipts.forEach(receipt => {
		const amount = parseAmount(receipt.totalAmount)
		const category = receipt.category || 'Other'
		
		calculatedTotalSpend += amount

		if (categoryBreakdown[category]) {
			categoryBreakdown[category].count += 1
			categoryBreakdown[category].totalSpend += amount
		} else {
			categoryBreakdown['Other'].count += 1
			categoryBreakdown['Other'].totalSpend += amount
		}
	})

	const maxCategorySpend = Math.max(...Object.values(categoryBreakdown).map(c => Object(c).totalSpend), 1)

	const totalReceipts = receipts.length
	const processingReceipts = receipts.filter(r => r.processingStatus === 'PROCESSING').length
	
	const matchedCount = receipts.filter(r => r.transactionMatchStatus === 'MATCHED').length
	const possibleMatchCount = receipts.filter(r => r.transactionMatchStatus === 'POSSIBLE_MATCH').length
	const unmatchedCount = receipts.filter(r => r.transactionMatchStatus === 'UNMATCHED').length
	const totalEvaluated = matchedCount + possibleMatchCount + unmatchedCount
	const matchRate = totalEvaluated > 0 ? ((matchedCount / totalEvaluated) * 100).toFixed(0) : '0'

	if (isLoading) {
		return (
			<main className="min-vh-100 bg-light d-flex align-items-center justify-content-center">
				<div className="spinner-border text-primary" role="status" />
			</main>
		)
	}

	return (
		<main className="min-vh-100 bg-light py-5">
			<div className="container">
				<div className="d-flex justify-content-between align-items-start flex-wrap gap-3 mb-4">
					<div>
						<p className="text-uppercase text-secondary fw-semibold mb-2">Live AWS Dashboard</p>
						<h1 className="h2 mb-0">Receipt timeline</h1>
					</div>
					<div className="d-flex flex-wrap gap-3">
						<Link to="/upload" className="btn btn-primary">Upload receipts</Link>
						<Link to="/user" className="btn btn-outline-secondary">User profile</Link>
					</div>
				</div>

				{errorMessage && <div className="alert alert-danger mb-4">{errorMessage}</div>}

				<div className="row g-4">
					<div className="col-12 col-xl-8">
						<div className="d-grid gap-4">
							{groupedMonths.length === 0 ? (
								<div className="p-5 bg-white border rounded-4 shadow-sm text-center">
									<p className="text-secondary mb-0">No documents indexed in your ledger. Upload your first financial receipt to start tracking!</p>
								</div>
							) : (
								groupedMonths.map((group) => (
									<section key={group.month} className="p-4 p-md-5 bg-white border rounded-4 shadow-sm">
										<div className="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-4">
											<h2 className="h4 mb-0 fw-bold text-dark">{group.month}</h2>
											<span className="badge text-bg-secondary">{group.items.length} records</span>
										</div>

										<div className="list-group list-group-flush">
										{group.items.map((item) => (
											<div key={item.receiptId} className="list-group-item px-0 py-3">
											<div className="row align-items-center g-3">
												
												<div className="col-12 col-md-7">
												<div className="fw-bold fs-5 text-dark text-truncate" title={item.merchantName}>
													{item.merchantName || 'Processing...'}
												</div>
												<div className="text-secondary small d-flex align-items-center gap-2 mt-1">
													<span style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>
													{item.receiptId.substring(0, 12)}...
													</span>
													<button 
													type="button" 
													className="btn btn-sm btn-link p-0 text-decoration-none text-primary"
													onClick={() => handleCopyId(item.receiptId)}
													>
													{copiedId === item.receiptId ? '✅' : '📋'}
													</button>
												</div>
												{item.matchedTransactionName && (
													<div className="mt-1 text-success small fw-bold">
													🔗 {item.matchedTransactionName}
													</div>
												)}
												</div>

												<div className="col-12 col-md-5 text-md-end">
												<div className="d-flex flex-wrap gap-2 justify-content-md-end align-items-center mb-2">
													<span className="badge text-bg-light border text-secondary">
													{item.receiptDate || 'No Date'}
													</span>
													<span className="badge text-bg-info text-dark">
													{item.category || 'Other'}
													</span>
													<span className={`badge ${item.transactionMatchStatus === 'MATCHED' ? 'text-bg-success' : 'text-bg-secondary'}`}>
													{item.transactionMatchStatus || 'PENDING'}
													</span>
													<span className="badge text-bg-dark fs-6">
													{item.totalAmount ? `$${item.totalAmount}` : '$-.--'}
													</span>
												</div>
												
												<div className="d-flex gap-2 justify-content-md-end">
													<Link 
														to={`/receipt?id=${encodeURIComponent(item.receiptId)}`}
														className="btn btn-sm btn-outline-primary"
													>
														👁️ View
													</Link>
													<Link 
														to={`/receipt?id=${encodeURIComponent(item.receiptId)}`}
														className="btn btn-sm btn-outline-secondary"
													>
														Summary
													</Link>
													<button 
														type="button" 
														className="btn btn-sm btn-outline-danger"
														onClick={() => handleDelete(item.receiptId)}
													>
														Delete
													</button>
												</div>
												</div>
											</div>
											</div>
										))}
										</div>
									</section>
								))
							)}
						</div>
					</div>

					<div className="col-12 col-xl-4 d-grid gap-4 align-self-start">
						
						<div className="p-4 bg-white border rounded-4 shadow-sm">
							<p className="text-uppercase text-secondary fw-semibold mb-2">Live Statistics</p>
							<div className="d-grid gap-3">
								<div>
									<div className="text-secondary small">Total volume velocity</div>
									<div className="h3 mb-0 fw-bold text-dark">${calculatedTotalSpend.toFixed(2)}</div>
								</div>
								<hr className="my-1" />
								<div className="row g-2">
									<div className="col-6">
										<div className="text-secondary small">Total documents</div>
										<div className="h5 mb-0">{totalReceipts}</div>
									</div>
									<div className="col-6">
										<div className="text-secondary small">In AI pipeline</div>
										<div className="h5 mb-0 text-warning">{processingReceipts}</div>
									</div>
								</div>
								<button type="button" className="btn btn-sm btn-outline-primary mt-2" onClick={() => loadData()}>
									🔄 Refresh Timeline
								</button>
							</div>
						</div>

						<div className="p-4 bg-white border rounded-4 shadow-sm">
							<p className="text-uppercase text-secondary fw-semibold mb-2">Bank Reconciliation</p>
							<p className="text-secondary small mb-3">Live linkage precision score mapping ledger inputs to third-party bank statements.</p>
							
							<div className="d-flex align-items-center gap-3 mb-3 p-3 bg-light rounded-3 border">
								<div className="display-5 fw-bold text-success">{matchRate}%</div>
								<div className="small lh-sm text-secondary">Overall ledger match rate probability</div>
							</div>

							<div className="d-grid gap-2 small">
								<div className="d-flex justify-content-between p-2 rounded-2 bg-light">
									<span className="text-success fw-semibold">✓ Fully Matched</span>
									<span className="badge text-bg-success">{matchedCount}</span>
								</div>
								<div className="d-flex justify-content-between p-2 rounded-2 bg-light">
									<span className="text-warning fw-semibold">⚠ Possible Matches</span>
									<span className="badge text-bg-warning text-dark">{possibleMatchCount}</span>
								</div>
								<div className="d-flex justify-content-between p-2 rounded-2 bg-light">
									<span className="text-danger fw-semibold">✗ Unmatched / Missing</span>
									<span className="badge text-bg-danger">{unmatchedCount}</span>
								</div>
							</div>
						</div>

						<div className="p-4 bg-white border rounded-4 shadow-sm">
							<p className="text-uppercase text-secondary fw-semibold mb-2">Spend by Category</p>
							<p className="text-secondary small mb-3">Asynchronous classification analytics driven by AWS Bedrock AI models.</p>
							<div className="d-grid gap-3">
								{Object.entries(categoryBreakdown).map(([category, data]) => {
									const percentage = (data.totalSpend / maxCategorySpend) * 100
									if (data.count === 0) return null

									return (
										<div key={category} className="small">
											<div className="d-flex justify-content-between align-items-center mb-1">
												<span className="fw-semibold text-dark">{category} ({data.count})</span>
												<span className="text-secondary fw-bold">${data.totalSpend.toFixed(2)}</span>
											</div>
											<div className="progress" style={{ height: '6px' }}>
												<div 
													className="progress-bar bg-primary rounded-pill" 
													role="progressbar" 
													style={{ width: `${percentage}%` }}
												/>
											</div>
										</div>
									)
								})}
							</div>
						</div>

						<div className="p-4 bg-white border rounded-4 shadow-sm">
							<p className="text-uppercase text-secondary fw-semibold mb-2">Bank Connection</p>
							{isBankConnected ? (
								<div className="text-start">
									<div className="alert alert-success py-2 px-3 small mb-2 d-flex align-items-center gap-2">
										<span className="fs-5">🏦</span> <strong>Plaid Connected</strong>
									</div>
									<p className="text-secondary small mb-0">Your transactions are successfully syncing with FinSight automatically.</p>
								</div>
							) : (
								<div className="text-start">
									<div className="alert alert-warning py-2 px-3 small mb-2">
										⚠️ <strong>Action Required</strong>
									</div>
									<p className="text-secondary small mb-3">Please link your bank account via Plaid Sandbox to verify your transactions.</p>
									<Link to="/user" className="btn btn-sm btn-primary w-100">
										Go Connect Bank
									</Link>
								</div>
							)}
						</div>
					</div>
				</div>
			</div>

		</main>
	)
}