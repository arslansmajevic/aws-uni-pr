// apps/web/src/App.tsx
import { Route, Routes } from 'react-router-dom'
import { HomePage } from './pages/homepage/HomePage'
import { LoginPage } from './pages/auth/LoginPage'
import { RegisterPage } from './pages/auth/RegisterPage'
import { UserPage } from './pages/user/UserPage'
import { ReceiptUploadPage } from './pages/receipt/ReceiptUploadPage'
import { UserDashboardPage } from './pages/receipt/UserDashboardPage'
import { ReceiptSummary } from './pages/receipt/ReceiptSummary'
import { ProtectedRoute } from './components/ProtectedRoute'
import { ChangePasswordPage } from './pages/user/ChangePasswordPage'
import { ForgotPasswordPage } from './pages/auth/ForgotPasswordPage'
import { ManageSharingPage } from './pages/sharing/ManageSharingPage'
import { SharedReceiptsPage } from './pages/sharing/SharedReceiptsPage'
import { SharedOwnerReceiptsPage } from './pages/sharing/SharedOwnerReceiptsPage'

function App() {
  return (
    <Routes>
      {/* Public routes - no token required */}
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* Protected routes - token required */}
      <Route
        path="/user"
        element={
          <ProtectedRoute>
            <UserPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/upload"
        element={
          <ProtectedRoute>
            <ReceiptUploadPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <UserDashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/receipt"
        element={
          <ProtectedRoute>
            <ReceiptSummary />
          </ProtectedRoute>
        }
      />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route
        path="/sharing"
        element={
          <ProtectedRoute>
            <ManageSharingPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/shared"
        element={
          <ProtectedRoute>
            <SharedReceiptsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/shared/:ownerId"
        element={
          <ProtectedRoute>
            <SharedOwnerReceiptsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/change-password"
        element={
          <ProtectedRoute>
            <ChangePasswordPage />
          </ProtectedRoute>
        }
      />

      {/* Fallback to homepage */}
      <Route path="*" element={<HomePage />} />
    </Routes>
  )
}

export default App