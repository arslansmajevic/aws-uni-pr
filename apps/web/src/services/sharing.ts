// apps/web/src/services/sharing.ts
import { getValidIdToken } from './authentication'
import type { ReceiptSummaryResponse } from './receipts'

type AppConfig = {
	apiUrl: string
}

async function loadConfig(): Promise<AppConfig> {
	const response = await fetch('/config.json', { cache: 'no-store' })
	if (!response.ok) {
		throw new Error(`Failed to load config.json: ${response.status}`)
	}
	return (await response.json()) as AppConfig
}

function apiBase(config: AppConfig): string {
	return config.apiUrl.replace(/\/$/, '')
}

async function authorizedFetch(path: string, init: RequestInit = {}): Promise<Response> {
	const config = await loadConfig()
	const token = await getValidIdToken()

	if (!token) {
		throw new Error('Not authenticated')
	}

	const headers: Record<string, string> = {
		Authorization: token,
		...(init.headers as Record<string, string> | undefined),
	}

	if (init.body) {
		headers['Content-Type'] = 'application/json'
	}

	return fetch(`${apiBase(config)}${path}`, { ...init, headers })
}

export type AppUser = {
	username: string
	email: string
	name: string
	sub: string
}

export type ShareViewer = {
	viewerId: string
	viewerEmail: string
	viewerName: string
}

export type SharedOwner = {
	ownerId: string
	ownerEmail: string
	ownerName: string
}

export async function listUsers(): Promise<AppUser[]> {
	const response = await authorizedFetch('/users', { method: 'GET' })

	if (!response.ok) {
		throw new Error('Failed to load users')
	}

	const data = await response.json()
	const users = (data.users || []) as Array<Record<string, string>>

	return users
		.map((user) => {
			const given = user.given_name || ''
			const family = user.family_name || ''
			const name = `${given} ${family}`.trim() || user.email || user.username
			return {
				username: user.username,
				email: user.email || '',
				name,
				sub: user.sub || user.username,
			}
		})
		.filter((user) => Boolean(user.sub))
}

export async function listShares(): Promise<ShareViewer[]> {
	const response = await authorizedFetch('/shares', { method: 'GET' })

	if (!response.ok) {
		throw new Error('Failed to load shared users')
	}

	const data = await response.json()
	return (data.viewers || []) as ShareViewer[]
}

export async function addShare(viewer: ShareViewer): Promise<void> {
	const response = await authorizedFetch('/shares', {
		method: 'POST',
		body: JSON.stringify(viewer),
	})

	if (!response.ok) {
		const errorData = await response.json().catch(() => ({}))
		throw new Error(errorData.message || 'Failed to share receipts')
	}
}

export async function removeShare(viewerId: string): Promise<void> {
	const response = await authorizedFetch(`/shares/${encodeURIComponent(viewerId)}`, {
		method: 'DELETE',
	})

	if (!response.ok) {
		const errorData = await response.json().catch(() => ({}))
		throw new Error(errorData.message || 'Failed to remove shared user')
	}
}

export async function listSharedWithMe(): Promise<SharedOwner[]> {
	const response = await authorizedFetch('/shared-with-me', { method: 'GET' })

	if (!response.ok) {
		throw new Error('Failed to load people sharing with you')
	}

	const data = await response.json()
	return (data.owners || []) as SharedOwner[]
}

export async function getSharedReceipts(ownerId: string): Promise<any[]> {
	const response = await authorizedFetch(
		`/shared/${encodeURIComponent(ownerId)}/receipts`,
		{ method: 'GET' }
	)

	if (!response.ok) {
		const errorData = await response.json().catch(() => ({}))
		throw new Error(errorData.message || 'Failed to load shared receipts')
	}

	const data = await response.json()
	return (data.receipts || []) as any[]
}

export async function getSharedReceiptSummary(
	ownerId: string,
	receiptId: string
): Promise<ReceiptSummaryResponse> {
	const response = await authorizedFetch(
		`/shared/${encodeURIComponent(ownerId)}/receipts/${encodeURIComponent(receiptId)}`,
		{ method: 'GET' }
	)

	if (!response.ok) {
		const errorData = await response.json().catch(() => ({}))
		throw new Error(errorData.message || 'Failed to load shared receipt summary')
	}

	return (await response.json()) as ReceiptSummaryResponse
}
