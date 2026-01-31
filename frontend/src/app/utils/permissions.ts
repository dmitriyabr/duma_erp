import type { AuthUser } from '../auth/authStorage'

/**
 * Centralized permission helpers. Use instead of inline user?.role === 'SuperAdmin'.
 * Aligns with CLAUDE.md role capabilities.
 */

export function isSuperAdmin(user: AuthUser | null): boolean {
  return user?.role === 'SuperAdmin'
}

export function canCancelPayment(user: AuthUser | null): boolean {
  return user?.role === 'SuperAdmin'
}

export function canApproveClaim(user: AuthUser | null): boolean {
  return user?.role === 'SuperAdmin'
}

export function canApproveGRN(user: AuthUser | null): boolean {
  return user?.role === 'SuperAdmin'
}

export function canManageReservations(user: AuthUser | null): boolean {
  return user?.role === 'SuperAdmin' || user?.role === 'Admin'
}

export function canManageStock(user: AuthUser | null): boolean {
  return user?.role === 'SuperAdmin' || user?.role === 'Admin'
}

export function canCreateItem(user: AuthUser | null): boolean {
  return user?.role === 'SuperAdmin'
}

export function canCancelIssuance(user: AuthUser | null): boolean {
  return user?.role === 'SuperAdmin'
}

export function canInvoiceTerm(user: AuthUser | null): boolean {
  return user?.role === 'SuperAdmin'
}

/** Accountant is read-only: no create/edit. */
export function isAccountant(user: AuthUser | null): boolean {
  return user?.role === 'Accountant'
}

/** Dashboard summary (cards, metrics): only Admin/SuperAdmin. User sees Quick Actions only. */
export function canSeeDashboardSummary(user: AuthUser | null): boolean {
  return user?.role === 'SuperAdmin' || user?.role === 'Admin'
}

/** Reports section (Aged Receivables, etc.): only Admin/SuperAdmin. */
export function canSeeReports(user: AuthUser | null): boolean {
  return user?.role === 'SuperAdmin' || user?.role === 'Admin'
}
