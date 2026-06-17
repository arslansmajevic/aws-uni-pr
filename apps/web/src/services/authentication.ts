type AppConfig = {
	apiUrl: string
}

export type RegisterUserRequest = {
	email: string
	password: string
	givenName: string
	familyName: string
}

type RegisterUserResponse = unknown

export type LoginUserRequest = {
	email: string
	password: string
}

export type LoginUserResponse = {
	AccessToken: string
	IdToken: string
	RefreshToken: string
	ExpiresIn: number
	TokenType: string
}

export type AuthTokens = {
	accessToken: string
	idToken: string
	refreshToken: string
	expiresIn: number
}

let configPromise: Promise<AppConfig> | null = null

async function loadConfig(): Promise<AppConfig> {
	if (!configPromise) {
		configPromise = fetch('/config.json', { cache: 'no-store' }).then(async (response) => {
			if (!response.ok) {
				throw new Error(`Failed to load config.json: ${response.status}`)
			}

			return (await response.json()) as AppConfig
		})
	}

	return configPromise
}

function buildUrl(apiUrl: string, path: string) {
	const normalizedPath = path.replace(/^\//, '')

	if (/^https?:\/\//i.test(apiUrl)) {
		return new URL(normalizedPath, apiUrl).toString()
	}

	return `${apiUrl.replace(/\/$/, '')}/${normalizedPath}`
}

export async function registerUser(payload: RegisterUserRequest): Promise<RegisterUserResponse> {
	const config = await loadConfig()
	const response = await fetch(buildUrl(config.apiUrl, 'register'), {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify(payload),
	})

	if (!response.ok) {
		throw new Error(`Register request failed: ${response.status}`)
	}

	const responseText = await response.text()
	return responseText ? (JSON.parse(responseText) as RegisterUserResponse) : null
}

export async function loginUser(payload: LoginUserRequest): Promise<AuthTokens> {
	const config = await loadConfig()
	const response = await fetch(buildUrl(config.apiUrl, 'login'), {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify(payload),
	})

	if (!response.ok) {
		throw new Error(`Login request failed: ${response.status}`)
	}

	const data = (await response.json()) as LoginUserResponse

	const tokens: AuthTokens = {
		accessToken: data.AccessToken,
		idToken: data.IdToken,
		refreshToken: data.RefreshToken,
		expiresIn: data.ExpiresIn,
	}

	// Store tokens in localStorage for now
	// In production, consider using secure httpOnly cookies
	localStorage.setItem('accessToken', tokens.accessToken)
	localStorage.setItem('idToken', tokens.idToken)
	localStorage.setItem('refreshToken', tokens.refreshToken)
	localStorage.setItem('expiresIn', tokens.expiresIn.toString())

	return tokens
}

export type TokenClaims = {
	given_name?: string
	family_name?: string
	email?: string
	sub?: string
	cognito_username?: string
	cognito_user_status?: string
	iat?: number
	exp?: number
}

function decodeToken(token: string): TokenClaims | null {
	try {
		const parts = token.split('.')
		if (parts.length !== 3) return null

		const decoded = JSON.parse(atob(parts[1])) as TokenClaims
		return decoded
	} catch {
		return null
	}
}

function getTokenExpirationTime(token: string): number | null {
	const claims = decodeToken(token)
	if (!claims?.exp) {
		return null
	}

	return claims.exp * 1000
}

function isTokenExpiringSoon(token: string, thresholdMs = 5 * 60 * 1000): boolean {
	const expirationTime = getTokenExpirationTime(token)
	if (!expirationTime) {
		return false
	}

	return expirationTime - Date.now() <= thresholdMs
}

function storeTokens(tokens: AuthTokens): void {
	// Store tokens in localStorage for now
	// In production, consider using secure httpOnly cookies
	localStorage.setItem('accessToken', tokens.accessToken)
	localStorage.setItem('idToken', tokens.idToken)
	localStorage.setItem('refreshToken', tokens.refreshToken)
	localStorage.setItem('expiresIn', tokens.expiresIn.toString())
}

function readStoredTokens(): AuthTokens | null {
	const accessToken = localStorage.getItem('accessToken')
	const idToken = localStorage.getItem('idToken')
	const refreshToken = localStorage.getItem('refreshToken')
	const expiresIn = localStorage.getItem('expiresIn')

	if (!accessToken || !idToken || !refreshToken || !expiresIn) {
		return null
	}

	return {
		accessToken,
		idToken,
		refreshToken,
		expiresIn: parseInt(expiresIn, 10),
	}
}

async function refreshStoredTokens(): Promise<AuthTokens | null> {
	const currentTokens = readStoredTokens()
	if (!currentTokens?.refreshToken) {
		return null
	}

	try {
		const config = await loadConfig()
		const response = await fetch(buildUrl(config.apiUrl, 'refresh'), {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
			},
			body: JSON.stringify({ refreshToken: currentTokens.refreshToken }),
		})

		if (!response.ok) {
			logout()
			return null
		}

		const data = (await response.json()) as {
			AccessToken: string
			IdToken: string
			ExpiresIn: number
		}

		const refreshedTokens: AuthTokens = {
			accessToken: data.AccessToken,
			idToken: data.IdToken,
			refreshToken: currentTokens.refreshToken,
			expiresIn: data.ExpiresIn,
		}

		storeTokens(refreshedTokens)
		return refreshedTokens
	} catch {
		logout()
		return null
	}
}

export function getStoredTokens(): AuthTokens | null {
	return readStoredTokens()
}

export async function getValidStoredTokens(): Promise<AuthTokens | null> {
	const storedTokens = readStoredTokens()
	if (!storedTokens) {
		return null
	}

	if (isTokenExpiringSoon(storedTokens.accessToken)) {
		return await refreshStoredTokens()
	}

	return storedTokens
}

export async function getValidIdToken(): Promise<string | null> {
	const tokens = await getValidStoredTokens()
	return tokens?.idToken ?? null
}

export async function getValidUserClaims(): Promise<TokenClaims | null> {
	const tokens = await getValidStoredTokens()
	if (!tokens) {
		return null
	}

	return decodeToken(tokens.idToken)
}

export function logout(): void {
	localStorage.removeItem('accessToken')
	localStorage.removeItem('idToken')
	localStorage.removeItem('refreshToken')
	localStorage.removeItem('expiresIn')
	localStorage.removeItem('isBankConnected')
}

export type ChangePasswordRequest = {
	previousPassword: string
	newPassword: string
}

export async function changePassword(payload: ChangePasswordRequest): Promise<void> {
	const config = await loadConfig()
	const token = await getValidIdToken()

	// Cognito's ChangePassword call needs the access token, not the id token,
	// so we read it directly from storage here rather than via getValidIdToken.
	const accessToken = localStorage.getItem('accessToken')

	if (!token || !accessToken) {
		throw new Error('Not authenticated')
	}

	const response = await fetch(buildUrl(config.apiUrl, 'change-password'), {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			'Authorization': accessToken,
		},
		body: JSON.stringify(payload),
	})

	if (!response.ok) {
		const errorData = await response.json().catch(() => ({}))
		throw new Error(errorData.message || 'Failed to change password')
	}
}

export type ForgotPasswordRequest = {
	email: string
}

export async function requestPasswordReset(payload: ForgotPasswordRequest): Promise<void> {
	const config = await loadConfig()
	const response = await fetch(buildUrl(config.apiUrl, 'forgot-password'), {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify(payload),
	})

	if (!response.ok) {
		const errorData = await response.json().catch(() => ({}))
		throw new Error(errorData.message || 'Failed to request password reset')
	}
}

export type ConfirmPasswordResetRequest = {
	email: string
	confirmationCode: string
	newPassword: string
}

export async function confirmPasswordReset(payload: ConfirmPasswordResetRequest): Promise<void> {
	const config = await loadConfig()
	const response = await fetch(buildUrl(config.apiUrl, 'confirm-forgot-password'), {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
		},
		body: JSON.stringify(payload),
	})

	if (!response.ok) {
		const errorData = await response.json().catch(() => ({}))
		throw new Error(errorData.message || 'Failed to reset password')
	}
}
