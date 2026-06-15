// apps/web/src/pages/receipt/ReceiptUploadPage.tsx
import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { uploadReceipt } from '../../services/receipts'

export function ReceiptUploadPage() {
  const navigate = useNavigate()
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]) 
  const [isUploading, setIsUploading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

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

          <form onSubmit={handleSubmit}>
            <div className="border border-2 border-dashed rounded-4 bg-light text-center p-5">
              <div className="row justify-content-center">
                <div className="col-12 col-xl-8">
                  <p className="display-6 mb-2">Select your receipts</p>
                  <p className="text-secondary mb-4">You can choose multiple images (JPEG, PNG) at once.</p>
                  
                  <input 
                    id="receipt-file" 
                    type="file" 
                    className="form-control form-control-lg" 
                    accept="image/jpeg,image/png"
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
                      {isUploading ? 'Uploading everything...' : 'Upload all receipts'}
                    </button>
                    <button type="button" className="btn btn-outline-secondary btn-lg" onClick={handleClear} disabled={isUploading}>
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