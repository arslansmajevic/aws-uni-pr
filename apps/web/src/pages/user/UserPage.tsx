// apps/web/src/pages/user/UserPage.tsx
import { Link } from 'react-router-dom'

export function UserPage() {
	return (
		<main className="min-vh-100 bg-light py-5">
			<div className="container">
				<div className="row justify-content-center g-4">
					<div className="col-12 col-lg-4">
						<div className="p-4 bg-white border rounded-4 shadow-sm h-100">
							<div className="d-flex align-items-center gap-3 mb-4">
								<div className="rounded-circle bg-primary text-white d-flex align-items-center justify-content-center fw-semibold flex-shrink-0 p-3">
									JD
								</div>
								<div>
									<p className="text-uppercase text-secondary fw-semibold mb-1">User profile</p>
									<h1 className="h4 mb-0">Jane Doe</h1>
								</div>
							</div>

							<div className="d-grid gap-3">
								<div className="p-3 bg-light border rounded-3">
									<div className="text-secondary small">Email</div>
									<div className="fw-semibold">jane.doe@example.com</div>
								</div>
								<div className="p-3 bg-light border rounded-3">
									<div className="text-secondary small">User ID</div>
									<div className="fw-semibold">usr_10482</div>
								</div>
								<div className="p-3 bg-light border rounded-3">
									<div className="text-secondary small">Account status</div>
									<div className="fw-semibold text-success">Verified</div>
								</div>
								<div className="p-3 bg-light border rounded-3">
									<div className="text-secondary small">Member since</div>
									<div className="fw-semibold">14 June 2026</div>
								</div>
							</div>
						</div>
					</div>

					<div className="col-12 col-lg-8">
						<div className="p-4 p-md-5 bg-white border rounded-4 shadow-sm h-100">
							<div className="mb-4">
								<p className="text-uppercase text-secondary fw-semibold mb-2">Security</p>
								<h2 className="h3 mb-2">Password management</h2>
								<p className="text-secondary mb-0">
									Use the actions below to update or recover access to the account.
								</p>
							</div>

							<div className="row g-3 mb-4">
								<div className="col-12 col-md-6">
									<div className="p-4 bg-light border rounded-4 h-100">
										<h3 className="h5 mb-2">Change password</h3>
										<p className="text-secondary mb-3">
											Update the current password after a security check.
										</p>
										<button type="button" className="btn btn-primary">
											Open change password form
										</button>
									</div>
								</div>

								<div className="col-12 col-md-6">
									<div className="p-4 bg-light border rounded-4 h-100">
										<h3 className="h5 mb-2">Reset password</h3>
										<p className="text-secondary mb-3">
											Send a reset link if the user cannot access the current password.
										</p>
										<button type="button" className="btn btn-outline-primary">
											Send reset link
										</button>
									</div>
								</div>
							</div>

							<div className="d-flex flex-wrap gap-3">
								<Link to="/" className="btn btn-outline-secondary">
									Back to homepage
								</Link>
								<Link to="/login" className="btn btn-link text-decoration-none align-self-center px-0">
									Sign out
								</Link>
							</div>
						</div>
					</div>
				</div>
			</div>
		</main>
	)
}
