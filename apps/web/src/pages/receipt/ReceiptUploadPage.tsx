// apps/web/src/pages/receipt/ReceiptUploadPage.tsx
import { Link } from 'react-router-dom'

export function ReceiptUploadPage() {
	return (
		<main className="min-vh-100 bg-light py-5">
			<div className="container-fluid px-3 px-md-4 px-lg-5">
				<div className="p-4 p-md-5 bg-white border rounded-4 shadow-sm">
					<div className="d-flex justify-content-between align-items-center flex-wrap gap-3 mb-4">
						<div>
							<p className="text-uppercase text-secondary fw-semibold mb-2">Receipts</p>
							<h1 className="h2 mb-0">Upload a receipt</h1>
						</div>

						<div className="d-flex flex-wrap gap-3">
							<Link to="/" className="btn btn-outline-secondary">
								Back to homepage
							</Link>
							<Link to="/user" className="btn btn-outline-primary">
								View profile
							</Link>
						</div>
					</div>

					<p className="text-secondary mb-4">
						Drop a receipt image or choose a file to upload. This page is intentionally
						minimal and leaves metadata handling for later.
					</p>

					<form>
						<div className="border border-2 border-dashed rounded-4 bg-light text-center p-5">
							<div className="row justify-content-center">
								<div className="col-12 col-xl-8">
									<p className="display-6 mb-2">Drag and drop your receipt here</p>
									<p className="text-secondary mb-4">
										JPEG, PNG, or PDF. You can also browse for a file from your device.
									</p>
									<label className="form-label fw-semibold d-block text-start" htmlFor="receipt-file">
										Receipt file
									</label>
									<input id="receipt-file" type="file" className="form-control form-control-lg" />
									<div className="d-flex justify-content-center flex-wrap gap-3 mt-4">
										<button type="submit" className="btn btn-primary btn-lg">
											Upload receipt
										</button>
										<button type="button" className="btn btn-outline-secondary btn-lg">
											Clear selection
										</button>
									</div>
								</div>
							</div>
						</div>
					</form>
				</div>
			</div>
		</main>
	)
}
