// apps/web/src/pages/sharing/ManageSharingPage.tsx
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { getValidUserClaims } from '../../services/authentication'
import {
	addShare,
	listShares,
	listUsers,
	removeShare,
	type AppUser,
	type ShareViewer,
} from '../../services/sharing'

export function ManageSharingPage() {
	const [viewers, setViewers] = useState<ShareViewer[]>([])
	const [users, setUsers] = useState<AppUser[]>([])
	const [searchTerm, setSearchTerm] = useState('')
	const [isLoading, setIsLoading] = useState(true)
	const [errorMessage, setErrorMessage] = useState<string | null>(null)
	const [busyUserId, setBusyUserId] = useState<string | null>(null)
	const [currentUserId, setCurrentUserId] = useState<string | null>(null)

	async function loadData() {
		try {
			setIsLoading(true)
			setErrorMessage(null)
			const claims = await getValidUserClaims()
			setCurrentUserId(claims?.sub ?? null)
			const [viewerList, userList] = await Promise.all([listShares(), listUsers()])
			setViewers(viewerList)
			setUsers(userList)
		} catch (err) {
			setErrorMessage(err instanceof Error ? err.message : 'Failed to load sharing settings.')
		} finally {
			setIsLoading(false)
		}
	}

	useEffect(() => {
		loadData()
	}, [])

	const sharedIds = useMemo(() => new Set(viewers.map((v) => v.viewerId)), [viewers])

	const availableUsers = useMemo(() => {
		const term = searchTerm.trim().toLowerCase()
		return users
			.filter((user) => user.sub !== currentUserId && !sharedIds.has(user.sub))
			.filter((user) => {
				if (!term) return true
				return (
					user.name.toLowerCase().includes(term) ||
					user.email.toLowerCase().includes(term)
				)
			})
	}, [users, searchTerm, currentUserId, sharedIds])

	async function handleAdd(user: AppUser) {
		try {
			setBusyUserId(user.sub)
			setErrorMessage(null)
			const viewer: ShareViewer = {
				viewerId: user.sub,
				viewerEmail: user.email,
				viewerName: user.name,
			}
			await addShare(viewer)
			setViewers((prev) => [...prev, viewer])
		} catch (err) {
			setErrorMessage(err instanceof Error ? err.message : 'Failed to share receipts.')
		} finally {
			setBusyUserId(null)
		}
	}

	async function handleRemove(viewerId: string) {
		try {
			setBusyUserId(viewerId)
			setErrorMessage(null)
			await removeShare(viewerId)
			setViewers((prev) => prev.filter((v) => v.viewerId !== viewerId))
		} catch (err) {
			setErrorMessage(err instanceof Error ? err.message : 'Failed to remove user.')
		} finally {
			setBusyUserId(null)
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
						<p className="text-uppercase text-secondary fw-semibold mb-2">Sharing</p>
						<h1 className="h2 mb-1">Who can view my receipts</h1>
						<p className="text-secondary mb-0">Grant trusted users read-only access to your receipts.</p>
					</div>
					<div className="d-flex flex-wrap gap-2">
						<Link to="/shared" className="btn btn-outline-primary">Shared with me</Link>
						<Link to="/dashboard" className="btn btn-outline-secondary">Back to dashboard</Link>
					</div>
				</div>

				{errorMessage && <div className="alert alert-danger mb-4">{errorMessage}</div>}

				<div className="row g-4">
					<div className="col-12 col-lg-6">
						<div className="p-4 bg-white border rounded-4 shadow-sm h-100">
							<h2 className="h5 mb-3">People with access ({viewers.length})</h2>
							{viewers.length === 0 ? (
								<p className="text-secondary mb-0">You are not sharing your receipts with anyone yet.</p>
							) : (
								<ul className="list-group list-group-flush">
									{viewers.map((viewer) => (
										<li
											key={viewer.viewerId}
											className="list-group-item px-0 d-flex justify-content-between align-items-center gap-2"
										>
											<div className="text-truncate">
												<div className="fw-semibold text-truncate">{viewer.viewerName}</div>
												<div className="text-secondary small text-truncate">{viewer.viewerEmail}</div>
											</div>
											<button
												type="button"
												className="btn btn-sm btn-outline-danger flex-shrink-0"
												onClick={() => handleRemove(viewer.viewerId)}
												disabled={busyUserId === viewer.viewerId}
											>
												{busyUserId === viewer.viewerId ? 'Removing...' : 'Remove'}
											</button>
										</li>
									))}
								</ul>
							)}
						</div>
					</div>

					<div className="col-12 col-lg-6">
						<div className="p-4 bg-white border rounded-4 shadow-sm h-100">
							<h2 className="h5 mb-3">Add a user</h2>
							<input
								type="search"
								className="form-control mb-3"
								placeholder="Search users by name or email"
								value={searchTerm}
								onChange={(e) => setSearchTerm(e.target.value)}
							/>
							{availableUsers.length === 0 ? (
								<p className="text-secondary mb-0">No matching users available to add.</p>
							) : (
								<ul className="list-group list-group-flush" style={{ maxHeight: '420px', overflowY: 'auto' }}>
									{availableUsers.map((user) => (
										<li
											key={user.sub}
											className="list-group-item px-0 d-flex justify-content-between align-items-center gap-2"
										>
											<div className="text-truncate">
												<div className="fw-semibold text-truncate">{user.name}</div>
												<div className="text-secondary small text-truncate">{user.email}</div>
											</div>
											<button
												type="button"
												className="btn btn-sm btn-outline-primary flex-shrink-0"
												onClick={() => handleAdd(user)}
												disabled={busyUserId === user.sub}
											>
												{busyUserId === user.sub ? 'Adding...' : 'Add'}
											</button>
										</li>
									))}
								</ul>
							)}
						</div>
					</div>
				</div>
			</div>
		</main>
	)
}
