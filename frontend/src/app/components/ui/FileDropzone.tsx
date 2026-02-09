import { useCallback, useRef, useState, useId } from 'react'
import { cn } from '../../utils/cn'
import { Spinner } from './Spinner'

export interface FileDropzoneProps {
  /** Main label shown in the dropzone */
  title: string
  /** Optional helper line under the title */
  description?: string
  /** Accept attribute for the hidden file input */
  accept?: string
  /** Show selected/uploaded filename */
  fileName?: string | null
  /** Disable interaction */
  disabled?: boolean
  /** Show loading state */
  loading?: boolean
  /** Called with the selected/dropped file */
  onFileSelected: (file: File) => void | Promise<void>
  className?: string
}

export const FileDropzone = ({
  title,
  description = "Drag & drop a file here, or click to choose.",
  accept,
  fileName,
  disabled = false,
  loading = false,
  onFileSelected,
  className,
}: FileDropzoneProps) => {
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const id = useId()

  const pick = useCallback(() => {
    if (disabled || loading) return
    inputRef.current?.click()
  }, [disabled, loading])

  const handleFile = useCallback(
    async (file: File | undefined) => {
      if (!file || disabled || loading) return
      await onFileSelected(file)
    },
    [disabled, loading, onFileSelected]
  )

  return (
    <div className={className}>
      <input
        ref={inputRef}
        id={`file-${id}`}
        type="file"
        className="hidden"
        accept={accept}
        onChange={async (e) => {
          const file = e.target.files?.[0]
          // allow picking the same file again
          e.currentTarget.value = ''
          await handleFile(file)
        }}
      />

      <div
        className={cn(
          'rounded-xl border-2 border-dashed p-4 transition-colors',
          disabled || loading ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer',
          dragOver ? 'border-primary bg-primary/5' : 'border-slate-200 hover:border-primary-light'
        )}
        role="button"
        tabIndex={disabled || loading ? -1 : 0}
        onClick={pick}
        onKeyDown={(e) => {
          if (disabled || loading) return
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            pick()
          }
        }}
        onDragEnter={(e) => {
          e.preventDefault()
          if (disabled || loading) return
          setDragOver(true)
        }}
        onDragOver={(e) => {
          e.preventDefault()
          if (disabled || loading) return
          setDragOver(true)
        }}
        onDragLeave={(e) => {
          e.preventDefault()
          setDragOver(false)
        }}
        onDrop={async (e) => {
          e.preventDefault()
          setDragOver(false)
          if (disabled || loading) return
          const file = e.dataTransfer.files?.[0]
          await handleFile(file)
        }}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-sm font-medium text-slate-700">{title}</div>
            <div className="text-xs text-slate-500 mt-1">{description}</div>
            {fileName && (
              <div className="text-xs text-slate-600 mt-2">
                Selected: <span className="font-medium">{fileName}</span>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2">
            {loading ? <Spinner size="small" /> : <span className="text-xs text-slate-500">Click</span>}
          </div>
        </div>
      </div>
    </div>
  )
}


