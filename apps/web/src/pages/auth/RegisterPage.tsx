// apps/web/src/pages/auth/RegisterPage.tsx
import { Link } from 'react-router-dom'

export function RegisterPage() {
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

              <form className="d-grid gap-3">
                <div>
                  <label className="form-label" htmlFor="name">
                    Full name
                  </label>
                  <input id="name" type="text" className="form-control" placeholder="Jane Doe" />
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
                  />
                </div>

                <button type="submit" className="btn btn-primary btn-lg">
                  Create account
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