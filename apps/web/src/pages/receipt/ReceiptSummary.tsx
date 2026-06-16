// apps/web/src/pages/receipt/ReceiptSummary.tsx
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

type ReceiptItem = {
	name: string
	quantity: number
	price: number
}

const dummyReceiptItems: ReceiptItem[] = [
	{ name: 'Whole grain bread', quantity: 2, price: 3.5 },
	{ name: 'Organic eggs', quantity: 1, price: 6.9 },
	{ name: 'Greek yogurt', quantity: 3, price: 2.2 },
	{ name: 'Fresh berries', quantity: 2, price: 4.75 },
	{ name: 'Coffee beans', quantity: 1, price: 12.5 },
]

const dummyImageSvg = `
<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1200" viewBox="0 0 900 1200">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#f8fafc" />
      <stop offset="100%" stop-color="#e2e8f0" />
    </linearGradient>
  </defs>
  <rect width="900" height="1200" rx="36" fill="url(#bg)" />
  <rect x="90" y="70" width="720" height="1060" rx="28" fill="#ffffff" stroke="#cbd5e1" stroke-width="4" />
  <rect x="140" y="130" width="180" height="26" rx="13" fill="#0f172a" opacity="0.9" />
  <rect x="140" y="190" width="280" height="18" rx="9" fill="#94a3b8" />
  <rect x="140" y="230" width="220" height="18" rx="9" fill="#cbd5e1" />
  <line x1="140" y1="320" x2="760" y2="320" stroke="#e2e8f0" stroke-width="4" />
  <text x="140" y="380" font-family="Arial, sans-serif" font-size="42" font-weight="700" fill="#0f172a">Market Receipt</text>
  <text x="140" y="435" font-family="Arial, sans-serif" font-size="24" fill="#475569">Receipt ID: someId</text>
  <text x="140" y="480" font-family="Arial, sans-serif" font-size="24" fill="#475569">Date: 16 June 2026</text>
  <rect x="140" y="540" width="620" height="2" fill="#e2e8f0" />
  <text x="140" y="610" font-family="Arial, sans-serif" font-size="28" fill="#0f172a">Groceries</text>
  <text x="610" y="610" font-family="Arial, sans-serif" font-size="28" fill="#0f172a">$30.12</text>
  <text x="140" y="680" font-family="Arial, sans-serif" font-size="28" fill="#0f172a">Dining</text>
  <text x="610" y="680" font-family="Arial, sans-serif" font-size="28" fill="#0f172a">$18.40</text>
  <text x="140" y="750" font-family="Arial, sans-serif" font-size="28" fill="#0f172a">Other</text>
  <text x="610" y="750" font-family="Arial, sans-serif" font-size="28" fill="#0f172a">$12.50</text>
  <rect x="140" y="860" width="620" height="2" fill="#e2e8f0" />
  <text x="140" y="950" font-family="Arial, sans-serif" font-size="32" font-weight="700" fill="#0f172a">Total</text>
  <text x="610" y="950" font-family="Arial, sans-serif" font-size="32" font-weight="700" fill="#0f172a">$61.02</text>
  <circle cx="740" cy="178" r="26" fill="#0f172a" opacity="0.9" />
  <circle cx="740" cy="178" r="10" fill="#ffffff" />
</svg>
`

function formatCurrency(amount: number): string {
	return new Intl.NumberFormat('en-US', {
		style: 'currency',
		currency: 'USD',
	}).format(amount)
}

export function ReceiptSummary() {
	const [searchParams] = useSearchParams()
	const receiptId = searchParams.get('id') ?? 'someId'
	const [isExpanded, setIsExpanded] = useState(false)

	const receiptImage = useMemo(() => `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(dummyImageSvg.replaceAll('someId', receiptId))}`, [receiptId])

	const total = dummyReceiptItems.reduce((sum, item) => sum + item.quantity * item.price, 0)

	function handleDeleteReceipt() {
		window.alert(`Dummy delete action for receipt ${receiptId}`)
	}

	return (
		<main className="min-vh-100 bg-light py-5">
			<div className="container">
				<div className="d-flex justify-content-between align-items-start flex-wrap gap-3 mb-4">
					<div>
						<p className="text-uppercase text-secondary fw-semibold mb-2">Receipt summary</p>
						<h1 className="h2 mb-1">Receipt {receiptId}</h1>
						<p className="text-secondary mb-0">Dummy receipt detail view exposed at /receipt?id={receiptId}</p>
					</div>
					<div className="d-flex flex-wrap gap-2">
						<Link to="/dashboard" className="btn btn-outline-secondary">Back to dashboard</Link>
						<Link to="/user" className="btn btn-outline-primary">Profile</Link>
					</div>
				</div>

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
									alt={`Receipt preview ${receiptId}`}
									className="img-fluid rounded-4 border shadow-sm w-100"
									style={{ cursor: 'zoom-in' }}
								/>
							</button>

							<div className="d-flex flex-wrap gap-2">
								<a className="btn btn-primary" href={receiptImage} download={`receipt-${receiptId}.svg`}>
									Download picture
								</a>
								<button type="button" className="btn btn-outline-danger" onClick={handleDeleteReceipt}>
									Delete receipt
								</button>
							</div>

							<div className="p-3 bg-light border rounded-3 small text-secondary">
								Tap the image to expand it. This is dummy data for now.
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
								<div className="badge text-bg-dark fs-6">{formatCurrency(total)}</div>
							</div>

							<div className="list-group list-group-flush mb-4">
								{dummyReceiptItems.map((item) => {
									const lineTotal = item.quantity * item.price

									return (
										<div key={item.name} className="list-group-item px-0 py-3 d-flex justify-content-between align-items-start gap-3">
											<div>
												<div className="fw-semibold">{item.name}</div>
												<div className="text-secondary small">Qty {item.quantity} · {formatCurrency(item.price)} each</div>
											</div>
											<div className="fw-semibold text-nowrap">{formatCurrency(lineTotal)}</div>
										</div>
									)
								})}
							</div>

							<div className="p-4 bg-light border rounded-4 d-flex justify-content-between align-items-center">
								<div>
									<div className="text-secondary small text-uppercase fw-semibold">Total</div>
									<div className="h3 mb-0">{formatCurrency(total)}</div>
								</div>
								<div className="text-end text-secondary small">
									<div>Tax included</div>
									<div>Dummy receipt data</div>
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
							alt={`Expanded receipt preview ${receiptId}`}
							className="img-fluid rounded-4 border"
							style={{ maxHeight: '80vh' }}
						/>
					</div>
				</div>
			) : null}
		</main>
	)
}