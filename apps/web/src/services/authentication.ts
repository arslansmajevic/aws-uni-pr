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

export function getStoredTokens(): AuthTokens | null {
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

export function getUserClaims(): TokenClaims | null {
	const idToken = localStorage.getItem('idToken')
	if (!idToken) return null

	return decodeToken(idToken)
}

export function logout(): void {
	localStorage.removeItem('accessToken')
	localStorage.removeItem('idToken')
	localStorage.removeItem('refreshToken')
	localStorage.removeItem('expiresIn')
}
