export type BillingChildGender = 'male' | 'female'

export interface BillingAccountChildDraft {
  first_name: string
  last_name: string
  date_of_birth: string
  gender: BillingChildGender
  grade_id: string
  transport_zone_id: string
  guardian_name: string
  guardian_phone: string
  guardian_email: string
  enrollment_date: string
  notes: string
}

export type BillingAccountChildField = keyof BillingAccountChildDraft
export type BillingAccountChildErrors = Partial<Record<BillingAccountChildField, string>>

interface FamilyContactDefaults {
  guardian_name?: string
  guardian_phone?: string
  guardian_email?: string
}

export const createEmptyBillingChildDraft = (
  defaults: FamilyContactDefaults = {}
): BillingAccountChildDraft => ({
  first_name: '',
  last_name: '',
  date_of_birth: '',
  gender: 'male',
  grade_id: '',
  transport_zone_id: '',
  guardian_name: defaults.guardian_name ?? '',
  guardian_phone: defaults.guardian_phone ?? '',
  guardian_email: defaults.guardian_email ?? '',
  enrollment_date: new Date().toISOString().slice(0, 10),
  notes: '',
})

export const validateBillingChildDraft = (
  value: BillingAccountChildDraft,
  familyDefaults: FamilyContactDefaults = {}
): BillingAccountChildErrors => {
  const errors: BillingAccountChildErrors = {}

  if (!value.first_name.trim()) errors.first_name = 'First name is required.'
  if (!value.last_name.trim()) errors.last_name = 'Last name is required.'
  if (!value.grade_id) errors.grade_id = 'Select a grade.'

  const effectiveGuardianName = value.guardian_name.trim() || familyDefaults.guardian_name?.trim() || ''
  const effectiveGuardianPhone = value.guardian_phone.trim() || familyDefaults.guardian_phone?.trim() || ''

  if (!effectiveGuardianName) {
    errors.guardian_name = 'Provide guardian name on the billing contact or child.'
  }
  if (!effectiveGuardianPhone) {
    errors.guardian_phone = 'Provide guardian phone on the billing contact or child.'
  }

  return errors
}

export const buildBillingChildPayload = (value: BillingAccountChildDraft) => ({
  first_name: value.first_name.trim(),
  last_name: value.last_name.trim(),
  date_of_birth: value.date_of_birth || null,
  gender: value.gender,
  grade_id: Number(value.grade_id),
  transport_zone_id: value.transport_zone_id ? Number(value.transport_zone_id) : null,
  guardian_name: value.guardian_name.trim() || null,
  guardian_phone: value.guardian_phone.trim() || null,
  guardian_email: value.guardian_email.trim() || null,
  enrollment_date: value.enrollment_date || null,
  notes: value.notes.trim() || null,
})
