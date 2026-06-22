// apps/web/src/pages/sharing/SharedReceiptsPage.tsx
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { listSharedWithMe, type SharedOwner } from '../../services/sharing'

export function SharedReceiptsPage() {
	const [owners, setOwners] = useState<SharedOwner[]>([])
	const [searchTerm, setSearchTerm] = useState('')
	const [isLoading, setIsLoading] = useState(true)
	const [errorMessage, setErrorMessage] = useState<string | null>(null)

	useEffect(() => {
		let isMounted = true

		async function load() {
			try {
				setIsLoading(true)
				setErrorMessage(null)
				const data = await listSharedWithMe()
				if (isMounted) setOwners(data)
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
	}, [])

	const filteredOwners = useMemo(() => {
		const term = searchTerm.trim().toLowerCase()
		if (!term) return owners
		return owners.filter(
			(owner) =>
				(owner.ownerName || '').toLowerCase().includes(term) ||
				(owner.ownerEmail || '').toLowerCase().includes(term)
		)
	}, [owners, searchTerm])

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
						<p className="text-uppercase text-secondary fw-semibold mb-2">Shared receipts</p>
						<h1 className="h2 mb-1">People sharing with me</h1>
						<p className="text-secondary mb-0">Select a person to browse the receipts they shared with you.</p>
					</div>
					<div className="d-flex flex-wrap gap-2">
						<Link to="/sharing" className="btn btn-outline-primary">Manage my sharing</Link>
						<Link to="/dashboard" className="btn btn-outline-secondary">Back to dashboard</Link>
					</div>
				</div>

				{errorMessage && <div className="alert alert-danger mb-4">{errorMessage}</div>}

				<div className="p-4 bg-white border rounded-4 shadow-sm">
					<input
						type="search"
						className="form-control mb-4"
						placeholder="Search people by name or email"
						value={searchTerm}
						onChange={(e) => setSearchTerm(e.target.value)}
					/>

					{owners.length === 0 ? (
						<p className="text-secondary mb-0">Nobody is sharing their receipts with you yet.</p>
					) : filteredOwners.length === 0 ? (
						<p className="text-secondary mb-0">No people match your search.</p>
					) : (
						<div className="row g-3">
							{filteredOwners.map((owner) => (
								<div key={owner.ownerId} className="col-12 col-md-6 col-xl-4">
									<Link
										to={`/shared/${encodeURIComponent(owner.ownerId)}`}
										className="text-decoration-none"
									>
										<div className="p-3 border rounded-4 h-100 d-flex align-items-center gap-3 bg-light shared-owner-card">
											<div
												className="rounded-circle bg-primary text-white d-flex align-items-center justify-content-center fw-semibold flex-shrink-0"
												style={{ width: '46px', height: '46px' }}
											>
												{(owner.ownerName || owner.ownerEmail || '?').charAt(0).toUpperCase()}
											</div>
											<div className="text-truncate">
												<div className="fw-semibold text-dark text-truncate">{owner.ownerName || owner.ownerEmail}</div>
												<div className="text-secondary small text-truncate">{owner.ownerEmail}</div>
											</div>
										</div>
									</Link>
								</div>
							))}
						</div>
					)}
				</div>
			</div>
		</main>
	)
}
