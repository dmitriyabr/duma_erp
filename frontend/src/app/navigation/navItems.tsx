import DashboardIcon from '@mui/icons-material/Dashboard'
import GroupIcon from '@mui/icons-material/Group'
import ReceiptIcon from '@mui/icons-material/Receipt'
import ShoppingCartIcon from '@mui/icons-material/ShoppingCart'
import LocalShippingIcon from '@mui/icons-material/LocalShipping'
import PaymentsIcon from '@mui/icons-material/Payments'
import AssessmentIcon from '@mui/icons-material/Assessment'
import FactCheckIcon from '@mui/icons-material/FactCheck'
import SettingsIcon from '@mui/icons-material/Settings'
import DescriptionIcon from '@mui/icons-material/Description'
import FileDownloadIcon from '@mui/icons-material/FileDownload'
import type { ReactNode } from 'react'
import type { UserRole } from '../auth/authStorage'

export interface NavItem {
  label: string
  path: string
  icon?: ReactNode
  roles: UserRole[]
  children?: NavItem[]
}

const allRoles: UserRole[] = ['SuperAdmin', 'Admin', 'User', 'Accountant']
const adminRoles: UserRole[] = ['SuperAdmin', 'Admin']
const viewRoles: UserRole[] = ['SuperAdmin', 'Admin', 'Accountant']

/** Minimal nav for Accountant role (read-only: students, stock, billing, documents, export, audit). */
export const accountantNavItems: NavItem[] = [
  { label: 'Dashboard', path: '/', icon: <DashboardIcon />, roles: ['Accountant'] },
  { label: 'Students', path: '/students', icon: <GroupIcon />, roles: ['Accountant'] },
  { label: 'Stock', path: '/inventory/stock', icon: <ShoppingCartIcon />, roles: ['Accountant'] },
  {
    label: 'Billing',
    path: '/billing',
    icon: <ReceiptIcon />,
    roles: ['Accountant'],
    children: [
      { label: 'Terms', path: '/billing/terms', roles: ['Accountant'] },
      { label: 'Fixed Fees', path: '/billing/fixed-fees', roles: ['Accountant'] },
      { label: 'Catalog', path: '/billing/catalog', roles: ['Accountant'] },
    ],
  },
  {
    label: 'Documents',
    path: '/accountant/documents',
    icon: <DescriptionIcon />,
    roles: ['Accountant'],
    children: [
      { label: 'Incoming Payments', path: '/payments', roles: ['Accountant'] },
      { label: 'Students Invoices', path: '/billing/invoices', roles: ['Accountant'] },
      { label: 'Purchase Orders', path: '/procurement/orders', roles: ['Accountant'] },
      { label: 'Goods Received', path: '/procurement/grn', roles: ['Accountant'] },
      { label: 'Procurement Payments', path: '/procurement/payments', roles: ['Accountant'] },
      { label: 'Employee Expenses Claims', path: '/compensations/claims', roles: ['Accountant'] },
      { label: 'Employee Payouts', path: '/compensations/payouts', roles: ['Accountant'] },
    ],
  },
  { label: 'Data Export', path: '/accountant/export', icon: <FileDownloadIcon />, roles: ['Accountant'] },
  { label: 'Audit Trail', path: '/audit', icon: <FactCheckIcon />, roles: ['Accountant'] },
]

export const navItems: NavItem[] = [
  {
    label: 'Dashboard',
    path: '/',
    icon: <DashboardIcon />,
    roles: allRoles,
  },
  {
    label: 'Students',
    path: '/students',
    icon: <GroupIcon />,
    roles: viewRoles,
  },
  {
    label: 'Billing',
    path: '/billing',
    icon: <ReceiptIcon />,
    roles: viewRoles,
    children: [
      { label: 'Terms', path: '/billing/terms', roles: ['SuperAdmin'] },
      { label: 'Fixed Fees', path: '/billing/fixed-fees', roles: ['SuperAdmin'] },
      { label: 'Catalog', path: '/billing/catalog', roles: adminRoles },
    ],
  },
  {
    label: 'Warehouse',
    path: '/inventory',
    icon: <ShoppingCartIcon />,
    roles: allRoles,
    children: [
      { label: 'Items', path: '/inventory/items', roles: adminRoles },
      { label: 'Stock', path: '/inventory/stock', roles: allRoles },
      { label: 'Movements', path: '/inventory/movements', roles: allRoles },
      { label: 'Issuances', path: '/inventory/issuances', roles: adminRoles },
      { label: 'Reservations', path: '/inventory/reservations', roles: adminRoles },
      {
        label: 'Stock Count',
        path: '/inventory/inventory-count',
        roles: adminRoles,
      },
    ],
  },
  {
    label: 'Procurement',
    path: '/procurement',
    icon: <LocalShippingIcon />,
    roles: viewRoles,
    children: [
      { label: 'Purchase Orders', path: '/procurement/orders', roles: viewRoles },
      { label: 'Goods Received', path: '/procurement/grn', roles: viewRoles },
      { label: 'Payments', path: '/procurement/payments', roles: viewRoles },
    ],
  },
  {
    label: 'Compensations',
    path: '/compensations',
    icon: <PaymentsIcon />,
    roles: allRoles,
    children: [
      { label: 'Employee Expenses Claims', path: '/compensations/claims', roles: allRoles },
      { label: 'Payouts', path: '/compensations/payouts', roles: ['SuperAdmin'] },
    ],
  },
  {
    label: 'Reports',
    path: '/reports',
    icon: <AssessmentIcon />,
    roles: adminRoles,
    children: [
      { label: 'Profit & Loss', path: '/reports/profit-loss', roles: adminRoles },
      { label: 'Cash Flow', path: '/reports/cash-flow', roles: adminRoles },
      { label: 'Balance Sheet', path: '/reports/balance-sheet', roles: adminRoles },
      { label: 'Students Debt', path: '/reports/aged-receivables', roles: adminRoles },
      { label: 'Student Fees by Term', path: '/reports/student-fees', roles: adminRoles },
      { label: 'Collection Rate Trend', path: '/reports/collection-rate', roles: adminRoles },
      { label: 'Discount Analysis', path: '/reports/discount-analysis', roles: adminRoles },
    ],
  },
  {
    label: 'Audit Log',
    path: '/audit',
    icon: <FactCheckIcon />,
    roles: viewRoles,
  },
  {
    label: 'Settings',
    path: '/settings',
    icon: <SettingsIcon />,
    roles: adminRoles,
    children: [
      { label: 'Users', path: '/settings/users', roles: ['SuperAdmin'] },
      { label: 'Grades', path: '/settings/grades', roles: adminRoles },
      { label: 'School', path: '/settings/school', roles: adminRoles },
      { label: 'Transport Zones', path: '/settings/transport-zones', roles: ['SuperAdmin'] },
      { label: 'Payment Purposes', path: '/settings/payment-purposes', roles: ['SuperAdmin'] },
    ],
  },
]
