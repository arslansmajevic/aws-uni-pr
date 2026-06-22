// apps/web/src/pages/sharing/SharedOwnerReceiptsPage.tsx
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getSharedReceipts, listSharedWithMe, type SharedOwner } from '../../services/sharing'

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

export function SharedOwnerReceiptsPage() {
	const { ownerId = '' } = useParams<{ ownerId: string }>()
	const [receipts, setReceipts] = useState<any[]>([])
	const [owner, setOwner] = useState<SharedOwner | null>(null)
	const [isLoading, setIsLoading] = useState(true)
	const [errorMessage, setErrorMessage] = useState<string | null>(null)
	const [previewImageUrl, setPreviewImageUrl] = useState<string | null>(null)

	useEffect(() => {
		let isMounted = true

		async function load() {
			try {
				setIsLoading(true)
				setErrorMessage(null)
				const [receiptList, owners] = await Promise.all([
					getSharedReceipts(ownerId),
					listSharedWithMe().catch(() => [] as SharedOwner[]),
				])
				if (!isMounted) return
				setReceipts(receiptList)
				setOwner(owners.find((o) => o.ownerId === ownerId) ?? null)
			} catch (err) {
				if (isMounted) {
					setErrorMessage(err instanceof Error ? err.message : 'Failed to load shared receipts.')
				}
			} finally {
				if (isMounted) setIsLoading(false)
			}
		}

		load()
		return () => {
			isMounted = false
		}
	}, [ownerId])

	if (isLoading) {
		return (
			<main className="min-vh-100 bg-light d-flex align-items-center justify-content-center">
				<div className="spinner-border text-primary" role="status" />
			</main>
		)
	}

	const ownerLabel = owner?.ownerName || owner?.ownerEmail || 'Shared receipts'

	const sortedReceipts = [...receipts].sort((a, b) => {
		const dateA = a.receiptDate || ''
		const dateB = b.receiptDate || ''
		return dateB.localeCompare(dateA)
	})

	const groupedMonths: { month: string; items: any[] }[] = []
	sortedReceipts.forEach((receipt) => {
		const label = getMonthLabel(receipt.receiptDate)
		let existingGroup = groupedMonths.find((g) => g.month === label)
		if (!existingGroup) {
			existingGroup = { month: label, items: [] }
			groupedMonths.push(existingGroup)
		}
		existingGroup.items.push(receipt)
	})

	return (
		<main className="min-vh-100 bg-light py-5">
			<div className="container">
				<div className="d-flex justify-content-between align-items-start flex-wrap gap-3 mb-4">
					<div>
						<p className="text-uppercase text-secondary fw-semibold mb-2">Shared receipts</p>
						<h1 className="h2 mb-1">{ownerLabel}</h1>
						{owner?.ownerEmail && <p className="text-secondary mb-0">{owner.ownerEmail}</p>}
					</div>
					<Link to="/shared" className="btn btn-outline-secondary">Back to people</Link>
				</div>

				{errorMessage && <div className="alert alert-danger mb-4">{errorMessage}</div>}

				{groupedMonths.length === 0 ? (
					<div className="p-4 bg-white border rounded-4 shadow-sm">
						<p className="text-secondary mb-0">This person has no receipts to show.</p>
					</div>
				) : (
					<div className="d-grid gap-4">
						{groupedMonths.map((group) => (
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
													<div className="text-secondary small mt-1">
														{item.receiptDate || 'No date'}
													</div>
												</div>
												<div className="col-12 col-md-5 text-md-end">
													<div className="d-flex flex-wrap gap-2 justify-content-md-end align-items-center mb-2">
														<span className="badge text-bg-info text-dark">{item.category || 'Other'}</span>
														<span className="badge text-bg-dark fs-6">
															{item.totalAmount ? `$${item.totalAmount}` : '$-.--'}
														</span>
													</div>
													<div className="d-flex gap-2 justify-content-md-end">
														<button
															type="button"
															className="btn btn-sm btn-outline-primary"
															onClick={() => setPreviewImageUrl(item.imageUrl || null)}
															disabled={!item.imageUrl}
														>
															👁️ View
														</button>
														<Link
															to={`/shared/${encodeURIComponent(ownerId)}/${encodeURIComponent(item.receiptId)}`}
															className="btn btn-sm btn-outline-secondary"
														>
															Summary
														</Link>
													</div>
												</div>
											</div>
										</div>
									))}
								</div>
							</section>
						))}
					</div>
				)}
			</div>

			{previewImageUrl && (
				<div
					className="position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center"
					style={{ backgroundColor: 'rgba(0,0,0,0.75)', zIndex: 1060 }}
					onClick={() => setPreviewImageUrl(null)}
				>
					<div
						className="bg-white border rounded-4 p-3 shadow-lg position-relative d-flex flex-column m-3 align-items-center"
						style={{ maxWidth: '540px', width: '100%', maxHeight: '85vh' }}
						onClick={(e) => e.stopPropagation()}
					>
						<div className="d-flex justify-content-between align-items-center w-100 mb-2 border-b pb-2">
							<span className="fw-bold text-dark">📄 Receipt Document Preview</span>
							<button type="button" className="btn-close" onClick={() => setPreviewImageUrl(null)} />
						</div>
						<div className="w-100 overflow-auto bg-light rounded-3 p-2 text-center d-flex align-items-center justify-content-center" style={{ minHeight: '300px' }}>
							<img
								src={previewImageUrl}
								alt="Shared receipt source file"
								className="img-fluid rounded shadow-sm"
								style={{ maxHeight: '60vh', objectFit: 'contain' }}
							/>
						</div>
					</div>
				</div>
			)}
		</main>
	)
}
