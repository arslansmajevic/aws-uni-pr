import { Navigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { getValidStoredTokens } from '../services/authentication'

interface ProtectedRouteProps {
	children: ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
	const [isChecking, setIsChecking] = useState(true)
	const [isAllowed, setIsAllowed] = useState(false)

	useEffect(() => {
		let isMounted = true

		async function verifyAccess() {
			const tokens = await getValidStoredTokens()

			if (!isMounted) {
				return
			}

			setIsAllowed(Boolean(tokens))
			setIsChecking(false)
		}

		verifyAccess().catch(() => {
			if (isMounted) {
				setIsAllowed(false)
				setIsChecking(false)
			}
		})

		return () => {
			isMounted = false
		}
	}, [])

	if (isChecking) {
		return (
			<main className="min-vh-100 bg-light d-flex align-items-center justify-content-center">
				<div className="spinner-border text-primary" role="status" />
			</main>
		)
	}

	if (!isAllowed) {
		return <Navigate to="/login" replace />
	}

	return <>{children}</>
}
