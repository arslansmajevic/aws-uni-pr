import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { requestPasswordReset, confirmPasswordReset } from '../../services/authentication'

export function ForgotPasswordPage() {
	const navigate = useNavigate()
	const [step, setStep] = useState<'request' | 'confirm'>('request')

	const [email, setEmail] = useState('')
	const [confirmationCode, setConfirmationCode] = useState('')
	const [newPassword, setNewPassword] = useState('')
	const [confirmNewPassword, setConfirmNewPassword] = useState('')

	const [errorMessage, setErrorMessage] = useState<string | null>(null)
	const [successMessage, setSuccessMessage] = useState<string | null>(null)
	const [isSubmitting, setIsSubmitting] = useState(false)

	async function handleRequestCode(event: FormEvent<HTMLFormElement>) {
		event.preventDefault()
		setErrorMessage(null)
		setSuccessMessage(null)

		try {
			setIsSubmitting(true)
			await requestPasswordReset({ email })
			setSuccessMessage('If an account exists for this email, a reset code has been sent.')
			setStep('confirm')
		} catch (error) {
			setErrorMessage(error instanceof Error ? error.message : 'Failed to request password reset.')
		} finally {
			setIsSubmitting(false)
		}
	}

	async function handleConfirmReset(event: FormEvent<HTMLFormElement>) {
		event.preventDefault()
		setErrorMessage(null)
		setSuccessMessage(null)

		if (newPassword !== confirmNewPassword) {
			setErrorMessage('New passwords do not match.')
			return
		}

		try {
			setIsSubmitting(true)
			await confirmPasswordReset({ email, confirmationCode, newPassword })
			setSuccessMessage('Password reset successfully. Redirecting to login...')
			setTimeout(() => {
				navigate('/login')
			}, 1500)
		} catch (error) {
			setErrorMessage(error instanceof Error ? error.message : 'Failed to reset password.')
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
								<p className="text-uppercase text-secondary fw-semibold mb-2">Account recovery</p>
								<h1 className="h3 mb-2">Reset your password</h1>
								<p className="text-secondary mb-0">
									{step === 'request'
										? 'Enter your email to receive a reset code.'
										: 'Enter the code we sent you along with your new password.'}
								</p>
							</div>

							{step === 'request' ? (
								<form className="d-grid gap-3" onSubmit={handleRequestCode}>
									<div>
										<label className="form-label" htmlFor="reset-email">
											Email
										</label>
										<input
											id="reset-email"
											type="email"
											className="form-control"
											placeholder="name@example.com"
											value={email}
											onChange={(event) => setEmail(event.target.value)}
											required
										/>
									</div>

									{errorMessage ? <div className="alert alert-danger mb-0">{errorMessage}</div> : null}
									{successMessage ? <div className="alert alert-success mb-0">{successMessage}</div> : null}

									<button type="submit" className="btn btn-primary btn-lg" disabled={isSubmitting}>
										{isSubmitting ? 'Sending code...' : 'Send reset code'}
									</button>
								</form>
							) : (
								<form className="d-grid gap-3" onSubmit={handleConfirmReset}>
									<div>
										<label className="form-label" htmlFor="confirmation-code">
											Reset code
										</label>
										<input
											id="confirmation-code"
											type="text"
											className="form-control"
											value={confirmationCode}
											onChange={(event) => setConfirmationCode(event.target.value)}
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
										{isSubmitting ? 'Resetting password...' : 'Reset password'}
									</button>

									<button
										type="button"
										className="btn btn-link p-0 text-start"
										onClick={() => setStep('request')}
									>
										Didn't get a code? Send again
									</button>
								</form>
							)}

							<div className="mt-3">
								<Link to="/login" className="link-secondary text-decoration-none">
									Back to login
								</Link>
							</div>
						</div>
					</div>
				</div>
			</div>
		</main>
	)
}