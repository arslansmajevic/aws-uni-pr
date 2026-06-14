// apps/web/src/pages/homepage/HomePage.tsx
import { Link } from 'react-router-dom'

export function HomePage() {
	return (
		<main className="min-vh-100 bg-light">
			<div className="container py-5">
				<div className="row justify-content-center mb-4">
					<div className="col-12 col-lg-10">
						<div className="p-4 p-md-5 bg-white border rounded-4 shadow-sm">
							<span className="badge text-bg-primary mb-3">Personal finance dashboard</span>
							<h1 className="display-5 fw-semibold mb-3">
								Manage receipts, accounts, and cash flow in one place.
							</h1>
							<p className="lead text-secondary mb-4">
								This homepage is the entry point for the app. From here, you can jump
								into authentication, explore receipts, or plug in additional product
								areas as the frontend grows.
							</p>
							<div className="d-flex flex-wrap gap-3">
								<Link className="btn btn-primary btn-lg" to="/login">
									Go to login
								</Link>
								<Link className="btn btn-outline-primary btn-lg" to="/register">
									Create account
								</Link>
								<a className="btn btn-outline-secondary btn-lg" href="#features">
									Explore features
								</a>
							</div>
						</div>
					</div>
				</div>

				<div className="row g-4" id="features">
					<div className="col-12 col-lg-6">
						<div className="h-100 p-4 bg-white border rounded-4 shadow-sm">
							<h2 className="h4 mb-3">At a glance</h2>
							<div className="row g-3">
								<div className="col-12 col-sm-6">
									<div className="p-3 bg-light rounded-3 border h-100">
										<div className="fs-3 fw-bold text-primary">24/7</div>
										<div className="text-secondary">access to your financial workspace</div>
									</div>
								</div>
								<div className="col-12 col-sm-6">
									<div className="p-3 bg-light rounded-3 border h-100">
										<div className="fs-3 fw-bold text-primary">3</div>
										<div className="text-secondary">core areas ready for expansion</div>
									</div>
								</div>
							</div>
						</div>
					</div>

					<div className="col-12 col-lg-6">
						<div className="h-100 p-4 bg-white border rounded-4 shadow-sm">
							<h2 className="h4 mb-3">What you can add next</h2>
							<ul className="list-group list-group-flush">
								<li className="list-group-item px-0">Receipt upload and receipt history views</li>
								<li className="list-group-item px-0">Account linking and transaction syncing screens</li>
								<li className="list-group-item px-0">User profile and settings pages</li>
							</ul>
						</div>
					</div>
				</div>
			</div>
		</main>
	)
}
