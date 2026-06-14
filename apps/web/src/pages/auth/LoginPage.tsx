// apps/web/src/pages/auth/LoginPage.tsx
import { Link } from 'react-router-dom'

export function LoginPage() {
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

              <form className="d-grid gap-3">
                <div>
                  <label className="form-label" htmlFor="email">
                    Email
                  </label>
                  <input id="email" type="email" className="form-control" placeholder="name@example.com" />
                </div>

                <div>
                  <label className="form-label" htmlFor="password">
                    Password
                  </label>
                  <input id="password" type="password" className="form-control" placeholder="Your password" />
                </div>

                <button type="submit" className="btn btn-primary btn-lg">
                  Sign in
                </button>
              </form>

              <div className="mt-3">
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
