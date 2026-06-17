import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { changePassword } from '../../services/authentication'

export function ChangePasswordPage() {
	const navigate = useNavigate()
	const [previousPassword, setPreviousPassword] = useState('')
	const [newPassword, setNewPassword] = useState('')
	const [confirmNewPassword, setConfirmNewPassword] = useState('')
	const [errorMessage, setErrorMessage] = useState<string | null>(null)
	const [successMessage, setSuccessMessage] = useState<string | null>(null)
	const [isSubmitting, setIsSubmitting] = useState(false)

	async function handleSubmit(event: FormEvent<HTMLFormElement>) {
		event.preventDefault()
		setErrorMessage(null)
		setSuccessMessage(null)

		if (newPassword !== confirmNewPassword) {
			setErrorMessage('New passwords do not match.')
			return
		}

		try {
			setIsSubmitting(true)

			await changePassword({ previousPassword, newPassword })

			setSuccessMessage('Password changed successfully. Redirecting...')
			setPreviousPassword('')
			setNewPassword('')
			setConfirmNewPassword('')

			setTimeout(() => {
				navigate('/user')
			}, 1500)
		} catch (error) {
			setErrorMessage(error instanceof Error ? error.message : 'Failed to change password.')
		} finally {
			setIsSubmitting(false)
		}
	}

	return (
		<main className="min-vh-100 d-flex align-items-center bg-light">
			<div className="container py-5">
				<div className="row justify-content-center">
					<div className="col-12 col-md-8 col-lg-5">
						<div className="p-4 p-md-5 bg-white border rounded-4 shadow-sm">
							<div className="mb-4">
								<p className="text-uppercase text-secondary fw-semibold mb-2">Security</p>
								<h1 className="h3 mb-2">Change your password</h1>
								<p className="text-secondary mb-0">
									Enter your current password and choose a new one.
								</p>
							</div>

							<form className="d-grid gap-3" onSubmit={handleSubmit}>
								<div>
									<label className="form-label" htmlFor="previous-password">
										Current password
									</label>
									<input
										id="previous-password"
										type="password"
										className="form-control"
										value={previousPassword}
										onChange={(event) => setPreviousPassword(event.target.value)}
										required
									/>
								</div>

								<div>
									<label className="form-label" htmlFor="new-password">
										New password
									</label>
									<input
										id="new-password"
										type="password"
										className="form-control"
										value={newPassword}
										onChange={(event) => setNewPassword(event.target.value)}
										required
									/>
								</div>

								<div>
									<label className="form-label" htmlFor="confirm-new-password">
										Confirm new password
									</label>
									<input
										id="confirm-new-password"
										type="password"
										className="form-control"
										value={confirmNewPassword}
										onChange={(event) => setConfirmNewPassword(event.target.value)}
										required
									/>
								</div>

								{errorMessage ? <div className="alert alert-danger mb-0">{errorMessage}</div> : null}

								{successMessage ? <div className="alert alert-success mb-0">{successMessage}</div> : null}

								<button type="submit" className="btn btn-primary btn-lg" disabled={isSubmitting}>
									{isSubmitting ? 'Changing password...' : 'Change password'}
								</button>
							</form>

							<div className="mt-3">
								<Link to="/user" className="link-secondary text-decoration-none">
									Back to profile
								</Link>
							</div>
						</div>
					</div>
				</div>
			</div>
		</main>
	)
}