/**
 * Shared pagination and list size constants. Use these instead of magic numbers
 * so limits stay consistent with backend and are easy to change.
 */

/** Default page size for list tables (e.g. students, users, items). */
export const DEFAULT_PAGE_SIZE = 25

/** Max items in dropdowns (students, users) to avoid huge payloads. */
export const MAX_DROPDOWN_SIZE = 200

/** Limit for invoice/payment lists on student detail (one student). */
export const INVOICE_LIST_LIMIT = 200

/** Limit for payments list on student detail. */
export const PAYMENTS_LIST_LIMIT = 100

/** Limit for reservations and similar secondary lists. */
export const SECONDARY_LIST_LIMIT = 200

/** Limit for users/employees dropdowns and lists (e.g. PayoutsPage, forms). */
export const USERS_LIST_LIMIT = 100
