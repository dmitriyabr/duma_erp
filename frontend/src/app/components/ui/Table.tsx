import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '../../utils/cn'

export interface TableProps extends HTMLAttributes<HTMLTableElement> {
  children: ReactNode
}

export const Table = ({ className, children, ...props }: TableProps) => {
  return (
    <div className="overflow-x-auto">
      <table
        className={cn('w-full border-collapse text-sm text-slate-700', className)}
        {...props}
      >
        {children}
      </table>
    </div>
  )
}

export interface TableHeadProps extends HTMLAttributes<HTMLTableSectionElement> {
  children: ReactNode
}

export const TableHead = ({ className, children, ...props }: TableHeadProps) => {
  return (
    <thead className={cn('bg-slate-50', className)} {...props}>
      {children}
    </thead>
  )
}

export interface TableBodyProps extends HTMLAttributes<HTMLTableSectionElement> {
  children: ReactNode
}

export const TableBody = ({ className, children, ...props }: TableBodyProps) => {
  return (
    <tbody className={className} {...props}>
      {children}
    </tbody>
  )
}

export interface TableRowProps extends HTMLAttributes<HTMLTableRowElement> {
  children: ReactNode
  hover?: boolean
}

export const TableRow = ({ className, children, hover = true, ...props }: TableRowProps) => {
  return (
    <tr
      className={cn(
        'border-b border-slate-100 transition-colors',
        hover && 'hover:bg-slate-50',
        className
      )}
      {...props}
    >
      {children}
    </tr>
  )
}

export interface TableCellProps extends HTMLAttributes<HTMLTableCellElement> {
  children: ReactNode
  align?: 'left' | 'center' | 'right'
}

export const TableCell = ({
  className,
  children,
  align = 'left',
  ...props
}: TableCellProps) => {
  const alignStyles = {
    left: 'text-left',
    center: 'text-center',
    right: 'text-right',
  }

  return (
    <td
      className={cn('px-4 py-3 text-sm text-slate-700', alignStyles[align], className)}
      {...props}
    >
      {children}
    </td>
  )
}

export interface TableHeaderCellProps extends HTMLAttributes<HTMLTableCellElement> {
  children: ReactNode
  align?: 'left' | 'center' | 'right'
}

export const TableHeaderCell = ({
  className,
  children,
  align = 'left',
  ...props
}: TableHeaderCellProps) => {
  const alignStyles = {
    left: 'text-left',
    center: 'text-center',
    right: 'text-right',
  }

  return (
    <th
      className={cn(
        'px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-600 border-b-2 border-slate-200',
        alignStyles[align],
        className
      )}
      {...props}
    >
      {children}
    </th>
  )
}

export interface TablePaginationProps {
  page: number
  rowsPerPage: number
  count: number
  onPageChange: (page: number) => void
  onRowsPerPageChange: (rowsPerPage: number) => void
  rowsPerPageOptions?: number[]
}

export const TablePagination = ({
  page,
  rowsPerPage,
  count,
  onPageChange,
  onRowsPerPageChange,
  rowsPerPageOptions = [10, 25, 50, 100],
}: TablePaginationProps) => {
  const totalPages = Math.ceil(count / rowsPerPage)
  const startRow = page * rowsPerPage + 1
  const endRow = Math.min((page + 1) * rowsPerPage, count)

  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-slate-200">
      <div className="flex items-center gap-4">
        <span className="text-sm text-slate-600">
          Rows per page:
        </span>
        <select
          value={rowsPerPage}
          onChange={(e) => onRowsPerPageChange(Number(e.target.value))}
          className="px-3 py-1.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
        >
          {rowsPerPageOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        <span className="text-sm text-slate-600">
          {startRow}-{endRow} of {count}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page === 0}
          className="px-3 py-1.5 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Previous
        </button>
        <span className="text-sm text-slate-600">
          Page {page + 1} of {totalPages || 1}
        </span>
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages - 1}
          className="px-3 py-1.5 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Next
        </button>
      </div>
    </div>
  )
}


