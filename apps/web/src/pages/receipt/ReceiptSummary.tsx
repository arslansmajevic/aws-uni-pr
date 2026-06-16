// apps/web/src/pages/receipt/ReceiptSummary.tsx
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { deleteReceipt, getReceiptSummary, type ReceiptSummaryResponse } from '../../services/receipts'

type ReceiptItem = {
	name?: string | null
	quantity?: string | number | null
	price?: string | number | null
}

const fallbackImageSvg = `
<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1200" viewBox="0 0 900 1200">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#f8fafc" />
      <stop offset="100%" stop-color="#e2e8f0" />
    </linearGradient>
  </defs>
  <rect width="900" height="1200" rx="36" fill="url(#bg)" />
  <rect x="90" y="70" width="720" height="1060" rx="28" fill="#ffffff" stroke="#cbd5e1" stroke-width="4" />
  <text x="140" y="180" font-family="Arial, sans-serif" font-size="42" font-weight="700" fill="#0f172a">Receipt Preview</text>
  <text x="140" y="240" font-family="Arial, sans-serif" font-size="24" fill="#475569">No image available</text>
</svg>
`

function formatCurrency(amount: number, currency = 'USD'): string {
	return new Intl.NumberFormat('en-US', {
		style: 'currency',
		currency,
	}).format(amount)
}

function parseAmount(value: string | number | null | undefined): number {
	if (value === null || value === undefined) {
		return 0
	}

	const parsed = Number(String(value).replace(/[^0-9.-]/g, ''))
	return Number.isFinite(parsed) ? parsed : 0
}

export function ReceiptSummary() {
	const [searchParams] = useSearchParams()
	const receiptId = searchParams.get('id')
	const [receipt, setReceipt] = useState<ReceiptSummaryResponse | null>(null)
	const [isLoading, setIsLoading] = useState(true)
	const [errorMessage, setErrorMessage] = useState<string | null>(null)
	const [isExpanded, setIsExpanded] = useState(false)
	const [isDeleting, setIsDeleting] = useState(false)

	useEffect(() => {
		let isMounted = true

		async function loadReceipt() {
			if (!receiptId) {
				setErrorMessage('Missing receipt id in the URL.')
				setIsLoading(false)
				return
			}

			try {
				setIsLoading(true)
				setErrorMessage(null)
				const response = await getReceiptSummary(receiptId)

				if (isMounted) {
					setReceipt(response)
				}
			} catch (error) {
				if (isMounted) {
					setErrorMessage(error instanceof Error ? error.message : 'Failed to load receipt summary.')
				}
			} finally {
				if (isMounted) {
					setIsLoading(false)
				}
			}
		}

		loadReceipt()

		return () => {
			isMounted = false
		}
	}, [receiptId])

	const receiptItems: ReceiptItem[] = receipt?.receiptItems ?? []
	const currency = receipt?.currency || 'USD'
	const total = receiptItems.reduce((sum, item) => {
		const quantity = parseAmount(item.quantity)
		const price = parseAmount(item.price)
		return sum + quantity * price
	}, 0)
	const fallbackReceiptImage = useMemo(
		() => `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(fallbackImageSvg)}`,
		[]
	)
	const receiptImage = receipt?.imageUrl || fallbackReceiptImage

	async function handleDeleteReceipt() {
		if (!receiptId || !window.confirm('Delete this receipt?')) {
			return
		}

		try {
			setIsDeleting(true)
			await deleteReceipt(receiptId)
			window.location.href = '/dashboard'
		} catch (error) {
			window.alert(error instanceof Error ? error.message : 'Failed to delete receipt.')
		} finally {
			setIsDeleting(false)
		}
	}

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
						<p className="text-uppercase text-secondary fw-semibold mb-2">Receipt summary</p>
						<h1 className="h2 mb-1">Receipt {receiptId || 'unknown'}</h1>
						<p className="text-secondary mb-0">
							{receipt?.merchantName || 'Receipt detail loaded from the backend'}
						</p>
					</div>
					<div className="d-flex flex-wrap gap-2">
						<Link to="/dashboard" className="btn btn-outline-secondary">Back to dashboard</Link>
						<Link to="/user" className="btn btn-outline-primary">Profile</Link>
					</div>
				</div>

				{errorMessage ? <div className="alert alert-danger mb-4">{errorMessage}</div> : null}

				<div className="row g-4">
					<div className="col-12 col-lg-5">
						<div className="p-4 bg-white border rounded-4 shadow-sm h-100 d-grid gap-3">
							<button
								type="button"
								className="btn p-0 border-0 bg-transparent text-start"
								onClick={() => setIsExpanded(true)}
								aria-label="Expand receipt image"
							>
								<img
									src={receiptImage}
									alt={`Receipt preview ${receiptId || 'unknown'}`}
									className="img-fluid rounded-4 border shadow-sm w-100"
									style={{ cursor: 'zoom-in' }}
								/>
							</button>

							<div className="d-flex flex-wrap gap-2">
								<a className="btn btn-primary" href={receiptImage} download={`receipt-${receiptId || 'image'}.svg`}>
									Download picture
								</a>
								<button
									type="button"
									className="btn btn-outline-danger"
									onClick={handleDeleteReceipt}
									disabled={isDeleting}
								>
									{isDeleting ? 'Deleting...' : 'Delete receipt'}
								</button>
							</div>

							<div className="p-3 bg-light border rounded-3 small text-secondary">
								Tap the image to expand it. The page is now backed by /receipts/{receiptId || 'someId'}.
							</div>
						</div>
					</div>

					<div className="col-12 col-lg-7">
						<div className="p-4 p-md-5 bg-white border rounded-4 shadow-sm h-100">
							<div className="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-4">
								<div>
									<p className="text-uppercase text-secondary fw-semibold mb-2">Items</p>
									<h2 className="h3 mb-0">Receipt breakdown</h2>
								</div>
								<div className="badge text-bg-dark fs-6">
									{formatCurrency(parseAmount(receipt?.totalAmount) || total, currency)}
								</div>
							</div>

							<div className="list-group list-group-flush mb-4">
								{receiptItems.length === 0 ? (
									<div className="list-group-item px-0 py-3 text-secondary">
										No extracted items were returned for this receipt.
									</div>
								) : (
									receiptItems.map((item, index) => {
										const quantity = parseAmount(item.quantity)
										const price = parseAmount(item.price)
										const lineTotal = quantity * price

										return (
											<div key={`${item.name || 'item'}-${index}`} className="list-group-item px-0 py-3 d-flex justify-content-between align-items-start gap-3">
												<div>
													<div className="fw-semibold">{item.name || 'Item'}</div>
													<div className="text-secondary small">
														Qty {quantity || 1} · {formatCurrency(price || lineTotal, currency)} each
													</div>
												</div>
												<div className="fw-semibold text-nowrap">{formatCurrency(lineTotal || price, currency)}</div>
											</div>
										)
									})
								)}
							</div>

							<div className="p-4 bg-light border rounded-4 d-flex justify-content-between align-items-center">
								<div>
									<div className="text-secondary small text-uppercase fw-semibold">Total</div>
									<div className="h3 mb-0">{formatCurrency(parseAmount(receipt?.totalAmount) || total, currency)}</div>
								</div>
								<div className="text-end text-secondary small">
									<div>{receipt?.merchantName || 'Dummy receipt data'}</div>
									<div>{receipt?.receiptDate || 'No receipt date'}</div>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>

			{isExpanded ? (
				<div
					className="position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center"
					style={{ backgroundColor: 'rgba(15, 23, 42, 0.85)', zIndex: 1080 }}
					onClick={() => setIsExpanded(false)}
				>
					<div className="bg-white rounded-4 shadow-lg p-3 m-3" onClick={(event) => event.stopPropagation()}>
						<div className="d-flex justify-content-between align-items-center mb-2">
							<strong>Expanded receipt preview</strong>
							<button type="button" className="btn-close" aria-label="Close" onClick={() => setIsExpanded(false)} />
						</div>
						<img
							src={receiptImage}
							alt={`Expanded receipt preview ${receiptId || 'unknown'}`}
							className="img-fluid rounded-4 border"
							style={{ maxHeight: '80vh' }}
						/>
					</div>
				</div>
			) : null}
		</main>
	)
}