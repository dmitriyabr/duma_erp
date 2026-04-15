import { Button } from '../../../components/ui/Button'
import { Input } from '../../../components/ui/Input'
import { Select } from '../../../components/ui/Select'
import { Textarea } from '../../../components/ui/Textarea'
import type { GradeRef, TransportZoneRef } from '../../../contexts/ReferencedDataContext'
import type {
  BillingAccountChildDraft,
  BillingAccountChildErrors,
  BillingChildGender,
} from './billingAccountChildForm'

interface BillingAccountChildEditorProps {
  value: BillingAccountChildDraft
  onChange: (next: BillingAccountChildDraft) => void
  grades: GradeRef[]
  transportZones: TransportZoneRef[]
  title: string
  onRemove?: () => void
  removeLabel?: string
  errors?: BillingAccountChildErrors
  helperText?: string
}

export const BillingAccountChildEditor = ({
  value,
  onChange,
  grades,
  transportZones,
  title,
  onRemove,
  removeLabel = 'Remove child',
  errors = {},
  helperText,
}: BillingAccountChildEditorProps) => {
  const setField = <K extends keyof BillingAccountChildDraft>(
    field: K,
    nextValue: BillingAccountChildDraft[K]
  ) => {
    onChange({ ...value, [field]: nextValue })
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-medium text-slate-900">{title}</div>
          {helperText && <div className="text-sm text-slate-500 mt-1">{helperText}</div>}
        </div>
        {onRemove && (
          <Button type="button" variant="text" onClick={onRemove}>
            {removeLabel}
          </Button>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Input
          label="First name"
          value={value.first_name}
          onChange={(event) => setField('first_name', event.target.value)}
          error={errors.first_name}
          required
        />
        <Input
          label="Last name"
          value={value.last_name}
          onChange={(event) => setField('last_name', event.target.value)}
          error={errors.last_name}
          required
        />
        <Input
          label="Date of birth"
          type="date"
          value={value.date_of_birth}
          onChange={(event) => setField('date_of_birth', event.target.value)}
          error={errors.date_of_birth}
        />
        <Select
          value={value.gender}
          onChange={(event) => setField('gender', event.target.value as BillingChildGender)}
          label="Gender"
          error={errors.gender}
        >
          <option value="male">Male</option>
          <option value="female">Female</option>
        </Select>
        <Select
          value={value.grade_id}
          onChange={(event) => setField('grade_id', event.target.value)}
          label="Grade"
          error={errors.grade_id}
          required
        >
          <option value="">Select grade</option>
          {grades.map((grade) => (
            <option key={grade.id} value={String(grade.id)}>
              {grade.name}
            </option>
          ))}
        </Select>
        <Select
          value={value.transport_zone_id}
          onChange={(event) => setField('transport_zone_id', event.target.value)}
          label="Transport zone"
          error={errors.transport_zone_id}
        >
          <option value="">No transport</option>
          {transportZones.map((zone) => (
            <option key={zone.id} value={String(zone.id)}>
              {zone.zone_name}
            </option>
          ))}
        </Select>
        <Input
          label="Guardian name"
          value={value.guardian_name}
          onChange={(event) => setField('guardian_name', event.target.value)}
          error={errors.guardian_name}
          helperText="Optional if it matches the billing contact."
        />
        <Input
          label="Guardian phone"
          value={value.guardian_phone}
          onChange={(event) => setField('guardian_phone', event.target.value)}
          error={errors.guardian_phone}
          helperText="Optional if it matches the billing contact."
        />
        <Input
          label="Guardian email"
          value={value.guardian_email}
          onChange={(event) => setField('guardian_email', event.target.value)}
          error={errors.guardian_email}
          helperText="Optional if it matches the billing contact."
        />
        <Input
          label="Enrollment date"
          type="date"
          value={value.enrollment_date}
          onChange={(event) => setField('enrollment_date', event.target.value)}
          error={errors.enrollment_date}
        />
      </div>

      <Textarea
        label="Notes"
        value={value.notes}
        onChange={(event) => setField('notes', event.target.value)}
        rows={3}
      />
    </div>
  )
}
