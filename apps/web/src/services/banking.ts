// apps/web/src/services/banking.ts
import { getValidIdToken } from './authentication'

type AppConfig = {
	apiUrl: string
}

async function loadConfig(): Promise<AppConfig> {
	const response = await fetch('/config.json', { cache: 'no-store' })
	if (!response.ok) throw new Error(`Failed to load config.json`)
	return (await response.json()) as AppConfig
}

export async function savePlaidCredentials(clientId: string, secret: string): Promise<void> {
	const config = await loadConfig()
	const token = await getValidIdToken()

	if (!token) throw new Error('Not authenticated')

	const response = await fetch(`${config.apiUrl.replace(/\/$/, '')}/bank/config`, {
		method: 'POST',
		headers: {
			'Authorization': token,
			'Content-Type': 'application/json'
		},
		body: JSON.stringify({ clientId, secret })
	})

	if (!response.ok) {
		const errData = await response.json().catch(() => ({}))
		throw new Error(errData.message || 'Failed to securely store credentials on AWS')
	}
}

export async function getPlaidLinkToken(): Promise<string> {
	const config = await loadConfig()
	const token = await getValidIdToken()

	if (!token) throw new Error('Not authenticated')

	const response = await fetch(`${config.apiUrl.replace(/\/$/, '')}/bank/connect`, {
		method: 'POST',
		headers: {
			'Authorization': token,
			'Content-Type': 'application/json'
		}
	})

	if (!response.ok) throw new Error('Failed to initialize bank connection. Make sure credentials are saved.')
	const data = await response.json()
	return data.linkToken
}

export async function exchangePlaidPublicToken(publicToken: string): Promise<void> {
	const config = await loadConfig()
	const token = await getValidIdToken()

	if (!token) throw new Error('Not authenticated')

	const response = await fetch(`${config.apiUrl.replace(/\/$/, '')}/bank/exchange`, {
		method: 'POST',
		headers: {
			'Authorization': token,
			'Content-Type': 'application/json'
		},
		body: JSON.stringify({ publicToken })
	})

	if (!response.ok) {
		const errData = await response.json().catch(() => ({}))
		throw new Error(errData.message || 'Failed to exchange token')
	}
}

export async function disconnectBank(): Promise<void> {
	const config = await loadConfig()
	const token = await getValidIdToken()

	if (!token) throw new Error('Not authenticated')

	const response = await fetch(`${config.apiUrl.replace(/\/$/, '')}/bank/disconnect`, {
		method: 'POST',
		headers: {
			'Authorization': token,
			'Content-Type': 'application/json'
		}
	})

	if (!response.ok) {
		const errData = await response.json().catch(() => ({}))
		throw new Error(errData.message || 'Failed to disconnect bank account')
	}
}

export async function getBankStatus(): Promise<boolean> {
	const config = await loadConfig()
	const token = await getValidIdToken()

	if (!token) throw new Error('Not authenticated')

	const response = await fetch(`${config.apiUrl.replace(/\/$/, '')}/bank/status`, {
		method: 'GET',
		headers: {
			'Authorization': token,
		}
	})

	if (!response.ok) {
		throw new Error('Failed to fetch bank connection status')
	}

	const data = await response.json()
	return Boolean(data.connected)
}