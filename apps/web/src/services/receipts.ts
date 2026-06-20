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

export type MultiUploadResponse = {
	message: string
	receiptId: string
	keys: string[]
}

export type ReceiptSummaryItem = {
	name?: string | null
	quantity?: string | number | null
	price?: string | number | null
}

export type ReceiptSummaryResponse = {
	receiptId: string
	merchantName?: string | null
	receiptDate?: string | null
	receiptTime?: string | null
	category?: string | null
	totalAmount?: string | number | null
	currency?: string | null
	receiptItems?: ReceiptSummaryItem[]
	imageUrl?: string | null
	transactionMatchStatus?: string | null
	matchedTransactionName?: string | null
	matchedTransactionId?: string | null
	matchedAmount?: string | number | null
	matchedDate?: string | null
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

async function fileToBase64(file: File): Promise<string> {
	return new Promise<string>((resolve, reject) => {
		const reader = new FileReader()
		reader.readAsDataURL(file)
		reader.onload = () => {
			const result = reader.result as string
			resolve(result.split(',')[1])
		}
		reader.onerror = (error) => reject(error)
	})
}

export async function uploadReceiptMultiImage(files: File[]): Promise<MultiUploadResponse> {
	const config = await loadConfig()
	const token = await getValidIdToken()

	if (!token) {
		throw new Error('User is not authenticated. Please log in again.')
	}

	const images = await Promise.all(
		files.map(async (file) => ({
			fileName: file.name,
			contentType: file.type || 'application/octet-stream',
			imageBase64: await fileToBase64(file),
		}))
	)

	const response = await fetch(`${config.apiUrl.replace(/\/$/, '')}/image/multi`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			'Authorization': token,
		},
		body: JSON.stringify({ images }),
	})

	if (!response.ok) {
		const errorData = await response.json().catch(() => ({}))
		throw new Error(errorData.message || `Multi-image upload failed with status ${response.status}`)
	}

	return (await response.json()) as MultiUploadResponse
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

export async function getReceiptSummary(receiptId: string): Promise<ReceiptSummaryResponse> {
	const config = await loadConfig()
	const token = await getValidIdToken()

	if (!token) throw new Error('Not authenticated')

	const response = await fetch(`${config.apiUrl.replace(/\/$/, '')}/receipts/${receiptId}`, {
		method: 'GET',
		headers: {
			'Authorization': token,
		},
	})

	if (!response.ok) {
		const errorData = await response.json().catch(() => ({}))
		throw new Error(errorData.message || 'Failed to fetch receipt summary')
	}

	return (await response.json()) as ReceiptSummaryResponse
}