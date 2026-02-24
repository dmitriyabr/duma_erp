export const formatStudentNumberShort = (studentNumber: string): string => {
  // Expected backend format: STU-YYYY-NNNNNN (e.g. STU-2026-000123)
  // Display format requested: YYNNN, where NNN is the numeric part without leading zeros.
  const match = /^STU-(\d{4})-(\d+)$/.exec(studentNumber)
  if (!match) return studentNumber

  const year = Number(match[1])
  const numRaw = match[2]
  const num = String(Number(numRaw)) // removes leading zeros; "000000" -> "0"
  const yy = String(year % 100).padStart(2, '0')
  return `${yy}${num}`
}

