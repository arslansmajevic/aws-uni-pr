// apps/web/src/pages/auth/RegisterPage.tsx
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { registerUser } from '../../services/authentication'

export function RegisterPage() {
  const navigate = useNavigate()   
  const [givenName, setGivenName] = useState('')
  const [familyName, setFamilyName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErrorMessage(null)
    setSuccessMessage(null)

    if (password !== confirmPassword) {
      setErrorMessage('Passwords do not match.')
      return
    }

    try {
      setIsSubmitting(true)

      await registerUser({
        email,
        password,
        givenName,
        familyName,
      })

      setSuccessMessage('Account created successfully. Redirecting to login...')
      setTimeout(() => {
        navigate('/login')
      }, 1500)
      
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Registration failed.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="min-vh-100 d-flex align-items-center bg-light">
      <div className="container py-5">
        <div className="row justify-content-center">
          <div className="col-12 col-md-9 col-lg-6">
            <div className="p-4 p-md-5 bg-white border rounded-4 shadow-sm">
              <div className="mb-4">
                <p className="text-uppercase text-secondary fw-semibold mb-2">Get started</p>
                <h1 className="h3 mb-2">Create your account</h1>
                <p className="text-secondary mb-0">
                  Register to start using the dashboard and connect your finance tools.
                </p>
              </div>

              <form className="d-grid gap-3" onSubmit={handleSubmit}>
                <div>
                  <label className="form-label" htmlFor="given-name">
                    Given name
                  </label>
                  <input
                    id="given-name"
                    type="text"
                    className="form-control"
                    placeholder="Arslan"
                    value={givenName}
                    onChange={(event) => setGivenName(event.target.value)}
                    required
                  />
                </div>

                <div>
                  <label className="form-label" htmlFor="family-name">
                    Family name
                  </label>
                  <input
                    id="family-name"
                    type="text"
                    className="form-control"
                    placeholder="Smajevic"
                    value={familyName}
                    onChange={(event) => setFamilyName(event.target.value)}
                    required
                  />
                </div>

                <div>
                  <label className="form-label" htmlFor="register-email">
                    Email
                  </label>
                  <input
                    id="register-email"
                    type="email"
                    className="form-control"
                    placeholder="name@example.com"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    required
                  />
                </div>

                <div>
                  <label className="form-label" htmlFor="register-password">
                    Password
                  </label>
                  <input
                    id="register-password"
                    type="password"
                    className="form-control"
                    placeholder="Create a password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                  />
                </div>

                <div>
                  <label className="form-label" htmlFor="confirm-password">
                    Confirm password
                  </label>
                  <input
                    id="confirm-password"
                    type="password"
                    className="form-control"
                    placeholder="Repeat your password"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    required
                  />
                </div>

                {errorMessage ? <div className="alert alert-danger mb-0">{errorMessage}</div> : null}

                {successMessage ? <div className="alert alert-success mb-0">{successMessage}</div> : null}

                <button type="submit" className="btn btn-primary btn-lg" disabled={isSubmitting}>
                  {isSubmitting ? 'Creating account...' : 'Create account'}
                </button>
              </form>

              <div className="mt-3 d-flex gap-3 flex-wrap">
                <Link to="/login" className="link-primary text-decoration-none">
                  Already have an account?
                </Link>
                <Link to="/" className="link-secondary text-decoration-none">
                  Back to homepage
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}