// apps/web/src/services/receipts.ts
import { getValidIdToken } from './authentication'

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

export type UploadResponse = {
	message: string
	receiptId: string
	key: string
}

export async function uploadReceipt(file: File): Promise<UploadResponse> {
	const config = await loadConfig()
	const token = await getValidIdToken()

	if (!token) {
		throw new Error('User is not authenticated. Please log in again.')
	}

	const base64String = await new Promise<string>((resolve, reject) => {
		const reader = new FileReader()
		reader.readAsDataURL(file)
		reader.onload = () => {
			const result = reader.result as string
			const cleanBase64 = result.split(',')[1]
			resolve(cleanBase64)
		}
		reader.onerror = (error) => reject(error)
	})

	const response = await fetch(`${config.apiUrl.replace(/\/$/, '')}/image`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			'Authorization': token, 
		},
		body: JSON.stringify({
			fileName: file.name,
			contentType: file.type || 'application/octet-stream',
			imageBase64: base64String,
		}),
	})

	if (!response.ok) {
		const errorData = await response.json().catch(() => ({}))
		throw new Error(errorData.message || `Upload failed with status ${response.status}`)
	}

	return (await response.json()) as UploadResponse
}

export async function getReceipts(): Promise<any[]> {
	const config = await loadConfig()
	const token = await getValidIdToken()

	if (!token) throw new Error('Not authenticated')

	const response = await fetch(`${config.apiUrl.replace(/\/$/, '')}/receipts`, {
		method: 'GET',
		headers: {
			'Authorization': token,
		},
	})

	if (!response.ok) throw new Error('Failed to fetch receipts')
	
	const data = await response.json()
	return data.receipts || []
}


export async function deleteReceipt(receiptId: string): Promise<void> {
	const config = await loadConfig()
	const token = await getValidIdToken()

	if (!token) throw new Error('Not authenticated')

	const response = await fetch(`${config.apiUrl.replace(/\/$/, '')}/receipts/${receiptId}`, {
        method: 'DELETE',
        headers: { 'Authorization': token },
    })


	if (!response.ok) {
		const errorData = await response.json().catch(() => ({}))
		throw new Error(errorData.message || 'Failed to delete receipt')
	}
}