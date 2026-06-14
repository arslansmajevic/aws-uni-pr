// apps/web/src/App.tsx
import { Route, Routes } from 'react-router-dom'
import { HomePage } from './pages/homepage/HomePage'
import { LoginPage } from './pages/auth/LoginPage'
import { RegisterPage } from './pages/auth/RegisterPage'
import { UserPage } from './pages/user/UserPage'
import { ReceiptUploadPage } from './pages/receipt/ReceiptUploadPage'
import { UserDashboardPage } from './pages/receipt/UserDashboardPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/user" element={<UserPage />} />
      <Route path="/upload" element={<ReceiptUploadPage />} />
      <Route path="/dashboard" element={<UserDashboardPage />} />
      <Route path="*" element={<HomePage />} />
    </Routes>
  )
}

export default App