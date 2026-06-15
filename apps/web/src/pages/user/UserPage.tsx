// apps/web/src/pages/user/UserPage.tsx
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { getUserClaims, logout } from '../../services/authentication'
import { getPlaidLinkToken, exchangePlaidPublicToken } from '../../services/banking'

type UserInfo = {
    givenName: string
    familyName: string
    email: string
    userId: string
}

export function UserPage() {
    const navigate = useNavigate()
    const [userInfo, setUserInfo] = useState<UserInfo | null>(null)
    const [isLoading, setIsLoading] = useState(true)
    
    const [isBankConnected, setIsBankConnected] = useState(false)
    const [plaidLoading, setPlaidLoading] = useState(false)
    const [plaidError, setPlaidError] = useState<string | null>(null)

    useEffect(() => {
        const claims = getUserClaims()
        if (!claims || !claims.email) {
            navigate('/login')
            return
        }

        setUserInfo({
            givenName: claims.given_name || 'User',
            familyName: claims.family_name || '',
            email: claims.email,
            userId: claims.sub || claims.cognito_username || 'unknown',
        })

        setIsBankConnected(localStorage.getItem('isBankConnected') === 'true')
        setIsLoading(false)

        const script = document.createElement('script')
        script.src = 'https://cdn.plaid.com/link/v2/stable/link-initialize.js'
        script.async = true
        document.head.appendChild(script)

        return () => {
            document.head.removeChild(script)
        }
    }, [navigate])

    async function handleConnectBank() {
        try {
            setPlaidError(null)
            setPlaidLoading(true)
            
            const linkToken = await getPlaidLinkToken()
            
            if (!(window as any).Plaid) {
                throw new Error('Plaid Link SDK is still initializing. Please wait a moment.')
            }

            const handler = (window as any).Plaid.create({
                token: linkToken,
                onSuccess: async (publicToken: string, metadata: any) => {
                    try {
                        setPlaidLoading(true)
                        await exchangePlaidPublicToken(publicToken)
                        
                        localStorage.setItem('isBankConnected', 'true')
                        setIsBankConnected(true)
                        alert(`Successfully authenticated with ${metadata.institution?.name || 'Bank'} via AWS OAuth!`)
                    } catch (exchangeErr) {
                        setPlaidError(exchangeErr instanceof Error ? exchangeErr.message : 'Key exchange failed.')
                    } finally {
                        setPlaidLoading(false)
                    }
                },
                onLoad: () => setPlaidLoading(false),
                onExit: () => setPlaidLoading(false),
            })

            handler.open()

        } catch (err) {
            setPlaidError(err instanceof Error ? err.message : 'Failed to establish Plaid link connection.')
            setPlaidLoading(false)
        }
    }

    function handleDisconnectBank() {
        if (window.confirm("Disconnect your bank and clear credentials?")) {
            localStorage.removeItem('isBankConnected')
            setIsBankConnected(false)
        }
    }

    function handleLogout() {
        logout()
        navigate('/login')
    }

    if (isLoading || !userInfo) {
        return (
            <div className="min-vh-100 bg-light d-flex align-items-center justify-content-center">
                <div className="spinner-border text-primary" role="status" />
            </div>
        )
    }

    const initials = `${userInfo.givenName[0]}${userInfo.familyName[0]}`.toUpperCase()

    return (
        <main className="min-vh-100 bg-light py-5">
            <div className="container">
                <div className="row justify-content-center g-4">
                    
                    <div className="col-12 col-lg-4">
                        <div className="p-4 bg-white border rounded-4 shadow-sm mb-4">
                            <div className="d-flex align-items-center gap-3 mb-4">
                                <div className="rounded-circle bg-primary text-white d-flex align-items-center justify-content-center fw-semibold p-3" style={{width: '50px', height: '50px'}}>
                                    {initials}
                                </div>
                                <div>
                                    <p className="text-uppercase text-secondary fw-semibold small mb-1">User profile</p>
                                    <h1 className="h4 mb-0">{userInfo.givenName} {userInfo.familyName}</h1>
                                </div>
                            </div>
                            <div className="p-3 bg-light border rounded-3 small fw-semibold text-truncate">
                                Email: {userInfo.email}
                            </div>
                        </div>

                        <div className="p-4 bg-white border rounded-4 shadow-sm">
                            <p className="text-uppercase text-secondary fw-semibold small mb-2">System Integrations</p>
                            <h3 className="h5 mb-3">Plaid API Connection</h3>
                            
                            {plaidError && <div className="alert alert-danger small py-2">{plaidError}</div>}

                            <div>
                                {isBankConnected ? (
                                    <div className="p-3 bg-light border border-success rounded-3 mb-3 small">
                                        <span className="text-success fw-bold">✓ Live Ledger Synced</span>
                                        <p className="text-secondary mb-0 mt-1">Token infrastructure securely managed inside AWS Secrets Manager.</p>
                                    </div>
                                ) : (
                                    <div className="p-3 bg-light border border-info rounded-3 mb-3 small">
                                        <span className="text-info fw-bold">ℹ Vault Credentials Ready</span>
                                        <p className="text-secondary mb-0 mt-1">AWS infrastructure is fully primed to accept tokens.</p>
                                    </div>
                                )}

                                {isBankConnected ? (
                                    <button type="button" className="btn btn-outline-danger w-100 btn-sm" onClick={handleDisconnectBank}>
                                        Disconnect Account Feed
                                    </button>
                                ) : (
                                    <button 
                                        type="button" 
                                        className="btn btn-primary w-100 mb-2 btn-sm" 
                                        onClick={handleConnectBank} 
                                        disabled={plaidLoading}
                                    >
                                        {plaidLoading ? 'Opening Portal...' : '🏦 Launch Plaid Link Frame'}
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>

                    <div className="col-12 col-lg-8">
                        <div className="p-4 p-md-5 bg-white border rounded-4 shadow-sm h-100">
                            <div className="mb-4">
                                <p className="text-uppercase text-secondary fw-semibold mb-2">Security</p>
                                <h2 className="h3 mb-2">Password management</h2>
                                <p className="text-secondary mb-0">Manage and maintain authentication tokens generated via Amazon Cognito.</p>
                            </div>

                            <div className="row g-3 mb-4">
                                <div className="col-12 col-md-6">
                                    <div className="p-4 bg-light border rounded-4 h-100">
                                        <h3 className="h5 mb-2">Change password</h3>
                                        <p className="text-secondary small mb-3">Update your account credentials after validating your active session token.</p>
                                        <button type="button" className="btn btn-primary btn-sm">Open form</button>
                                    </div>
                                </div>
                                <div className="col-12 col-md-6">
                                    <div className="p-4 bg-light border rounded-4 h-100">
                                        <h3 className="h5 mb-2">Reset password</h3>
                                        <p className="text-secondary small mb-3">Initiate an out-of-band account recovery flow using secure Cognito email challenges.</p>
                                        <button type="button" className="btn btn-outline-primary btn-sm">Send link</button>
                                    </div>
                                </div>
                            </div>

                            <div className="d-flex flex-wrap gap-3 pt-3 border-top">
                                <Link to="/dashboard" className="btn btn-outline-secondary">Return to Dashboard</Link>
                                <button type="button" className="btn btn-link text-decoration-none px-0 align-self-center ms-auto" onClick={handleLogout}>Sign out</button>
                            </div>
                        </div>
                    </div>

                </div>
            </div>
        </main>
    )
}