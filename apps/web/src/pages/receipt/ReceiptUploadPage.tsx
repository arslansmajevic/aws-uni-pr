// apps/web/src/pages/receipt/ReceiptUploadPage.tsx
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { uploadReceipt, uploadReceiptMultiImage } from '../../services/receipts'

export function ReceiptUploadPage() {
  const navigate = useNavigate()

  // --- Single-receipt upload state ---
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  // --- Multi-image single-receipt upload state ---
  const [multiFiles, setMultiFiles] = useState<File[]>([])
  const [isMultiUploading, setIsMultiUploading] = useState(false)
  const [multiError, setMultiError] = useState<string | null>(null)
  const [multiSuccess, setMultiSuccess] = useState<string | null>(null)

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    if (event.target.files && event.target.files.length > 0) {
      setSelectedFiles(Array.from(event.target.files))
      setErrorMessage(null)
      setSuccessMessage(null)
    }
  }

  function handleClear() {
    setSelectedFiles([])
    setErrorMessage(null)
    setSuccessMessage(null)
    const fileInput = document.getElementById('receipt-file') as HTMLInputElement
    if (fileInput) fileInput.value = ''
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (selectedFiles.length === 0) {
      setErrorMessage('Please select at least one receipt file.')
      return
    }

    setErrorMessage(null)
    setSuccessMessage(null)
    setIsUploading(true)

    try {
      await Promise.all(selectedFiles.map(file => uploadReceipt(file)))
      
      setSuccessMessage(`Successfully uploaded ${selectedFiles.length} receipts! Redirecting...`)
      setSelectedFiles([])

      setTimeout(() => {
        navigate('/dashboard')
      }, 2000)

    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'An error occurred during upload.')
    } finally {
      setIsUploading(false)
    }
  }

  function handleMultiFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    if (event.target.files && event.target.files.length > 0) {
      setMultiFiles(Array.from(event.target.files))
      setMultiError(null)
      setMultiSuccess(null)
    }
  }

  function handleMultiClear() {
    setMultiFiles([])
    setMultiError(null)
    setMultiSuccess(null)
    const fileInput = document.getElementById('multi-receipt-file') as HTMLInputElement
    if (fileInput) fileInput.value = ''
  }

  async function handleMultiSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (multiFiles.length < 2) {
      setMultiError('Please select at least 2 images for a multi-image receipt.')
      return
    }

    setMultiError(null)
    setMultiSuccess(null)
    setIsMultiUploading(true)

    try {
      const result = await uploadReceiptMultiImage(multiFiles)
      setMultiSuccess(
        `${multiFiles.length} images uploaded and queued as one receipt (ID: ${result.receiptId}). Redirecting...`
      )
      setMultiFiles([])

      setTimeout(() => {
        navigate('/dashboard')
      }, 2000)
    } catch (error) {
      setMultiError(error instanceof Error ? error.message : 'An error occurred during upload.')
    } finally {
      setIsMultiUploading(false)
    }
  }

  return (
    <main className="min-vh-100 bg-light py-5">
      <div className="container-fluid px-3 px-md-4 px-lg-5">
        <div className="p-4 p-md-5 bg-white border rounded-4 shadow-sm">
          <div className="d-flex justify-content-between align-items-center flex-wrap gap-3 mb-4">
            <div>
              <p className="text-uppercase text-secondary fw-semibold mb-2">Receipts</p>
              <h1 className="h2 mb-0">Upload receipts</h1>
            </div>
            <div className="d-flex flex-wrap gap-3">
              <Link to="/dashboard" className="btn btn-outline-secondary">Back to dashboard</Link>
            </div>
          </div>

          {/* ── Section 1: one file = one receipt ── */}
          <form onSubmit={handleSubmit}>
            <div className="border border-2 border-dashed rounded-4 bg-light text-center p-5 mb-4">
              <div className="row justify-content-center">
                <div className="col-12 col-xl-8">
                  <p className="display-6 mb-2">Select your receipts</p>
                  <p className="text-secondary mb-4">
                    Each selected file becomes a separate receipt.
                    Supports JPEG, PNG, TIFF, and PDF.
                  </p>
                  
                  <input 
                    id="receipt-file" 
                    type="file" 
                    className="form-control form-control-lg" 
                    accept="image/jpeg,image/png,image/tiff,application/pdf"
                    onChange={handleFileChange}
                    disabled={isUploading}
                    multiple 
                    required
                  />

                  {selectedFiles.length > 0 && (
                    <div className="mt-3 text-start alert alert-info">
                      <strong>Selected files ({selectedFiles.length}):</strong>
                      <ul className="mb-0 mt-2 max-vh-25 overflow-auto">
                        {selectedFiles.map((file, idx) => (
                          <li key={idx}>{file.name} ({(file.size / 1024).toFixed(1)} KB)</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {errorMessage && <div className="alert alert-danger mt-3 mb-0 text-start">{errorMessage}</div>}
                  {successMessage && <div className="alert alert-success mt-3 mb-0 text-start">{successMessage}</div>}

                  <div className="d-flex justify-content-center flex-wrap gap-3 mt-4">
                    <button type="submit" className="btn btn-primary btn-lg" disabled={isUploading || selectedFiles.length === 0}>
                      {isUploading ? 'Uploading...' : 'Upload all receipts'}
                    </button>
                    <button type="button" className="btn btn-outline-secondary btn-lg" onClick={handleClear} disabled={isUploading}>
                      Clear
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </form>

          <hr className="my-2" />

          {/* ── Section 2: multiple images = one receipt ── */}
          <form onSubmit={handleMultiSubmit}>
            <div className="border border-2 border-dashed rounded-4 bg-light text-center p-5 mt-4">
              <div className="row justify-content-center">
                <div className="col-12 col-xl-8">
                  <p className="display-6 mb-2">Multi-image receipt</p>
                  <p className="text-secondary mb-4">
                    Select <strong>multiple images that belong to the same receipt</strong> (e.g.&nbsp;
                    front and back, or a long receipt split across pages). All images will be
                    processed together as a single receipt. Minimum 2 images.
                  </p>

                  <input
                    id="multi-receipt-file"
                    type="file"
                    className="form-control form-control-lg"
                    accept="image/jpeg,image/png,image/tiff,application/pdf"
                    onChange={handleMultiFileChange}
                    disabled={isMultiUploading}
                    multiple
                    required
                  />

                  {multiFiles.length > 0 && (
                    <div className="mt-3 text-start alert alert-info">
                      <strong>Selected images ({multiFiles.length}) — will be merged into one receipt:</strong>
                      <ul className="mb-0 mt-2 max-vh-25 overflow-auto">
                        {multiFiles.map((file, idx) => (
                          <li key={idx}>{file.name} ({(file.size / 1024).toFixed(1)} KB)</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {multiError && <div className="alert alert-danger mt-3 mb-0 text-start">{multiError}</div>}
                  {multiSuccess && <div className="alert alert-success mt-3 mb-0 text-start">{multiSuccess}</div>}

                  <div className="d-flex justify-content-center flex-wrap gap-3 mt-4">
                    <button
                      type="submit"
                      className="btn btn-success btn-lg"
                      disabled={isMultiUploading || multiFiles.length < 2}
                    >
                      {isMultiUploading ? 'Uploading...' : 'Upload as one receipt'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-outline-secondary btn-lg"
                      onClick={handleMultiClear}
                      disabled={isMultiUploading}
                    >
                      Clear
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </form>
        </div>
      </div>
    </main>
  )
}