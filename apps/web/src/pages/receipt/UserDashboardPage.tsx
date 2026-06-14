// apps/web/src/pages/receipt/UserDashboardPage.tsx
import { useState } from 'react'
import { Link } from 'react-router-dom'

type ReceiptItem = {
	id: string
	merchant: string
	timestamp: string
	verified: boolean
	saved: boolean
	amount: string
	transactionId?: string
}

type ReceiptMonth = {
	month: string
	items: ReceiptItem[]
}

const receiptMonths: ReceiptMonth[] = [
	{
		month: 'June 2026',
		items: [
			{
				id: 'r-1049',
				merchant: 'Metro Grocery',
				timestamp: '14 Jun 2026, 18:42',
				verified: true,
				saved: true,
				amount: '€42.18',
				transactionId: 'txn_9f2c81a4',
			},
			{
				id: 'r-1048',
				merchant: 'City Rail',
				timestamp: '13 Jun 2026, 09:15',
				verified: true,
				saved: false,
				amount: '€7.60',
				transactionId: 'txn_2a7d41be',
			},
			{
				id: 'r-1047',
				merchant: 'Paper & Co',
				timestamp: '02 Jun 2026, 11:03',
				verified: false,
				saved: true,
				amount: '€18.90',
			},
		],
	},
	{
		month: 'May 2026',
		items: [
			{
				id: 'r-1046',
				merchant: 'North Cafe',
				timestamp: '29 May 2026, 08:24',
				verified: true,
				saved: true,
				amount: '€5.70',
				transactionId: 'txn_7c3ab0d9',
			},
			{
				id: 'r-1045',
				merchant: 'Office Depot',
				timestamp: '18 May 2026, 16:11',
				verified: false,
				saved: false,
				amount: '€126.50',
			},
			{
				id: 'r-1044',
				merchant: 'Quick Taxi',
				timestamp: '04 May 2026, 22:08',
				verified: true,
				saved: true,
				amount: '€24.20',
				transactionId: 'txn_0bd6f134',
			},
		],
	},
	{
		month: 'April 2026',
		items: [
			{
				id: 'r-1043',
				merchant: 'Home Supplies',
				timestamp: '27 Apr 2026, 12:30',
				verified: true,
				saved: true,
				amount: '€64.99',
			},
			{
				id: 'r-1042',
				merchant: 'Lunch Corner',
				timestamp: '10 Apr 2026, 13:14',
				verified: false,
				saved: false,
				amount: '€13.40',
				transactionId: 'txn_5ee18a72',
			},
		],
	},
]

export function UserDashboardPage() {
	const [copiedTransactionId, setCopiedTransactionId] = useState<string | null>(null)

	async function handleCopyTransactionId(transactionId: string) {
		try {
			await navigator.clipboard.writeText(transactionId)
			setCopiedTransactionId(transactionId)
			window.setTimeout(() => {
				setCopiedTransactionId((currentValue) =>
					currentValue === transactionId ? null : currentValue,
				)
			}, 1500)
		} catch {
			setCopiedTransactionId(null)
		}
	}

	return (
		<main className="min-vh-100 bg-light py-5">
			<div className="container">
				<div className="d-flex justify-content-between align-items-start flex-wrap gap-3 mb-4">
					<div>
						<p className="text-uppercase text-secondary fw-semibold mb-2">Receipts dashboard</p>
						<h1 className="h2 mb-0">Receipt timeline</h1>
					</div>

					<div className="d-flex flex-wrap gap-3">
						<Link to="/upload" className="btn btn-primary">
							Upload receipt
						</Link>
						<Link to="/user" className="btn btn-outline-secondary">
							User profile
						</Link>
					</div>
				</div>

				<div className="row g-4">
					<div className="col-12 col-xl-9">
						<div className="d-grid gap-4">
							{receiptMonths.map((monthGroup) => (
								<section key={monthGroup.month} className="p-4 p-md-5 bg-white border rounded-4 shadow-sm">
									<div className="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-4">
										<h2 className="h4 mb-0">{monthGroup.month}</h2>
										<span className="badge text-bg-secondary">{monthGroup.items.length} receipts</span>
									</div>

									<div className="list-group list-group-flush">
										{monthGroup.items.map((item) => (
											<div key={item.id} className="list-group-item px-0 py-3">
												<div className="d-flex flex-column flex-md-row justify-content-between gap-3">
													<div>
														<div className="fw-semibold mb-1">{item.merchant}</div>
														<div className="text-secondary small">{item.id}</div>
														{item.transactionId ? (
															(() => {
																const transactionId = item.transactionId

																return (
															<div className="mt-2">
																<div className="text-secondary small mb-1">Transaction ID</div>
																<button
																	type="button"
																	className={`btn btn-sm font-monospace ${
																			copiedTransactionId === transactionId
																			? 'btn-success'
																			: 'btn-outline-primary'
																	}`}
																		onClick={() => handleCopyTransactionId(transactionId)}
																		aria-label={`Copy transaction ID ${transactionId}`}
																>
																		{copiedTransactionId === transactionId
																		? 'Copied to clipboard'
																			: transactionId}
																</button>
															</div>
																)
															})()
														) : null}
													</div>

													<div className="d-flex flex-wrap gap-2 align-items-center">
														<span className="badge text-bg-light border text-secondary">
															{item.timestamp}
														</span>
														<span className={`badge ${item.verified ? 'text-bg-success' : 'text-bg-warning'}`}>
															Verified: {item.verified ? 'Yes' : 'No'}
														</span>
														<span className={`badge ${item.saved ? 'text-bg-primary' : 'text-bg-secondary'}`}>
															Saved: {item.saved ? 'Yes' : 'No'}
														</span>
														<span className="badge text-bg-dark">{item.amount}</span>
													</div>
												</div>
											</div>
										))}
									</div>
								</section>
							))}
						</div>
					</div>

					<div className="col-12 col-xl-3">
						<div className="p-4 bg-white border rounded-4 shadow-sm h-100">
							<p className="text-uppercase text-secondary fw-semibold mb-2">Summary</p>
							<div className="d-grid gap-3">
								<div>
									<div className="text-secondary small">Total receipts</div>
									<div className="h4 mb-0">8</div>
								</div>
								<div>
									<div className="text-secondary small">Verified receipts</div>
									<div className="h4 mb-0">5</div>
								</div>
								<div>
									<div className="text-secondary small">Saved receipts</div>
									<div className="h4 mb-0">5</div>
								</div>
								<div>
									<div className="text-secondary small">Latest upload</div>
									<div className="fw-semibold">14 Jun 2026, 18:42</div>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</main>
	)
}
