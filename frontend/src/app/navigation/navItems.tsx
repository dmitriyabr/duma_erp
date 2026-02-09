import {
  LayoutDashboard,
  Users,
  Receipt,
  ShoppingCart,
  Truck,
  CreditCard,
  BarChart3,
  FileCheck,
  Settings,
  FileText,
  Download,
} from 'lucide-react'
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
const superAdminRoles: UserRole[] = ['SuperAdmin']

/** Minimal nav for Accountant role (read-only: students, stock, billing, documents, export, audit). */
export const accountantNavItems: NavItem[] = [
  { label: 'Dashboard', path: '/', icon: <LayoutDashboard className="w-5 h-5" />, roles: ['Accountant'] },
  { label: 'Students', path: '/students', icon: <Users className="w-5 h-5" />, roles: ['Accountant'] },
  { label: 'Stock', path: '/inventory/stock', icon: <ShoppingCart className="w-5 h-5" />, roles: ['Accountant'] },
  {
    label: 'Billing',
    path: '/billing',
    icon: <Receipt className="w-5 h-5" />,
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
    icon: <FileText className="w-5 h-5" />,
    roles: ['Accountant'],
    children: [
      { label: 'Incoming Payments', path: '/payments', roles: ['Accountant'] },
      { label: 'Students Invoices', path: '/billing/invoices', roles: ['Accountant'] },
      { label: 'Purchase Orders', path: '/procurement/orders', roles: ['Accountant'] },
      { label: 'Goods Received', path: '/procurement/grn', roles: ['Accountant'] },
      { label: 'Procurement Payments', path: '/procurement/payments', roles: ['Accountant'] },
      { label: 'Employee Expenses Claims', path: '/compensations/claims', roles: ['Accountant'] },
      { label: 'Employee Payouts', path: '/compensations/payouts', roles: ['Accountant'] },
      { label: 'Bank Statements', path: '/accountant/bank-statements', roles: ['Accountant'] },
    ],
  },
  { label: 'Data Export', path: '/accountant/export', icon: <Download className="w-5 h-5" />, roles: ['Accountant'] },
  { label: 'Audit Trail', path: '/audit', icon: <FileCheck className="w-5 h-5" />, roles: ['Accountant'] },
]

export const navItems: NavItem[] = [
  {
    label: 'Dashboard',
    path: '/',
    icon: <LayoutDashboard className="w-5 h-5" />,
    roles: allRoles,
  },
  {
    label: 'Students',
    path: '/students',
    icon: <Users className="w-5 h-5" />,
    roles: viewRoles,
  },
  {
    label: 'Billing',
    path: '/billing',
    icon: <Receipt className="w-5 h-5" />,
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
    icon: <ShoppingCart className="w-5 h-5" />,
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
    icon: <Truck className="w-5 h-5" />,
    roles: viewRoles,
    children: [
      { label: 'Purchase Orders', path: '/procurement/orders', roles: viewRoles },
      { label: 'Goods Received', path: '/procurement/grn', roles: viewRoles },
      { label: 'Payments', path: '/procurement/payments', roles: viewRoles },
      { label: 'Bank Reconciliation', path: '/bank-reconciliation', roles: ['SuperAdmin'] },
    ],
  },
  {
    label: 'Compensations',
    path: '/compensations',
    icon: <CreditCard className="w-5 h-5" />,
    roles: allRoles,
    children: [
      { label: 'Employee Expenses Claims', path: '/compensations/claims', roles: allRoles },
      { label: 'Payouts', path: '/compensations/payouts', roles: viewRoles },
    ],
  },
  {
    label: 'Reports',
    path: '/reports',
    icon: <BarChart3 className="w-5 h-5" />,
    roles: adminRoles,
    children: [
      { label: 'Financial', path: '/reports/financial', roles: adminRoles },
      { label: 'Students', path: '/reports/students', roles: adminRoles },
      { label: 'Procurement & Inventory', path: '/reports/procurement', roles: adminRoles },
      { label: 'Compensations', path: '/reports/compensations', roles: adminRoles },
      { label: 'Analytics', path: '/reports/analytics', roles: adminRoles },
    ],
  },
  {
    label: 'Audit Log',
    path: '/audit',
    icon: <FileCheck className="w-5 h-5" />,
    roles: viewRoles,
  },
  {
    label: 'Settings',
    path: '/settings',
    icon: <Settings className="w-5 h-5" />,
    roles: superAdminRoles,
    children: [
      { label: 'Users', path: '/settings/users', roles: ['SuperAdmin'] },
      { label: 'Grades', path: '/settings/grades', roles: superAdminRoles },
      { label: 'School', path: '/settings/school', roles: superAdminRoles },
      { label: 'Transport Zones', path: '/settings/transport-zones', roles: ['SuperAdmin'] },
      { label: 'Payment Purposes', path: '/settings/payment-purposes', roles: ['SuperAdmin'] },
    ],
  },
]
