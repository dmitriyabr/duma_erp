import assert from 'node:assert/strict'
import test from 'node:test'
import { formatApiErrorMessage } from '../src/app/utils/apiErrors.ts'

const apiError = (message, errors) => ({
  isAxiosError: true,
  message: 'Request failed with status code 422',
  response: { data: { message, errors } },
})

test('shows a business error only once when the API repeats it in details', () => {
  const message = 'This payment cannot be transferred.'
  assert.equal(formatApiErrorMessage(apiError(message, [{ field: null, message }])), message)
})

test('keeps distinct details and removes repeated summary text', () => {
  assert.equal(formatApiErrorMessage(apiError('Transfer failed', [
    { message: 'Transfer failed' }, { message: 'Choose another student' },
    { message: 'Choose another student' },
  ])), 'Transfer failed: Choose another student')
})

test('retains field labels for validation errors', () => {
  assert.equal(formatApiErrorMessage(apiError('Validation error', [
    { field: 'target_student_id', message: 'Student not found' },
    { field: 'reason', message: 'Required' },
  ])), 'target_student_id: Student not found; reason: Required')
})
