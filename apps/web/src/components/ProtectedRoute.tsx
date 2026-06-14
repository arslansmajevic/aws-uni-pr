import { Navigate } from 'react-router-dom'
import type { ReactNode } from 'react'
import { getStoredTokens } from '../services/authentication'

interface ProtectedRouteProps {
	children: ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
	const tokens = getStoredTokens()

	if (!tokens) {
		return <Navigate to="/login" replace />
	}

	return <>{children}</>
}
