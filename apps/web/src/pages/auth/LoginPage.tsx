// apps/web/src/pages/auth/LoginPage.tsx
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { loginUser } from '../../services/authentication'

export function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErrorMessage(null)
    setSuccessMessage(null)

    try {
      setIsSubmitting(true)

      await loginUser({
        email,
        password,
      })

      setSuccessMessage('Login successful! Redirecting...')
      setTimeout(() => {
        navigate('/dashboard')
      }, 1500)
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Login failed.')
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
                <p className="text-uppercase text-secondary fw-semibold mb-2">Welcome back</p>
                <h1 className="h3 mb-2">Sign in to your account</h1>
                <p className="text-secondary mb-0">
                  Use your email and password to access the dashboard.
                </p>
              </div>

              <form className="d-grid gap-3" onSubmit={handleSubmit}>
                <div>
                  <label className="form-label" htmlFor="email">
                    Email
                  </label>
                  <input
                    id="email"
                    type="email"
                    className="form-control"
                    placeholder="name@example.com"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    required
                  />
                </div>

                <div>
                  <label className="form-label" htmlFor="password">
                    Password
                  </label>
                  <input
                    id="password"
                    type="password"
                    className="form-control"
                    placeholder="Your password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                  />
                </div>

                {errorMessage ? <div className="alert alert-danger mb-0">{errorMessage}</div> : null}

                {successMessage ? <div className="alert alert-success mb-0">{successMessage}</div> : null}

                <button type="submit" className="btn btn-primary btn-lg" disabled={isSubmitting}>
                  {isSubmitting ? 'Signing in...' : 'Sign in'}
                </button>
              </form>

              <div className="mt-3">
                <Link to="/forgot-password" className="link-secondary text-decoration-none">
                  Forgot password?
                </Link>
                <Link to="/register" className="link-primary text-decoration-none me-3">
                  Create an account
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
