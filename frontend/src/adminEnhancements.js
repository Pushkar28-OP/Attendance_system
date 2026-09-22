import api from './services/api'

function downloadWorkbook(range, anchorDate) {
  return api.get(`/api/admin/export?range=${range}&date=${anchorDate}`, { responseType: 'blob' }).then(({ data }) => {
    const url = URL.createObjectURL(data)
    const link = document.createElement('a')
    link.href = url
    link.download = `aurelix-attendance-${range}-${anchorDate}.xlsx`
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  })
}

function selectedEmployeeId() {
  const editor = [...document.querySelectorAll('section')].find(section => section.textContent.includes('PEOPLE / EDIT RECORD'))
  return editor?.querySelector('input')?.value || ''
}

function syncAdminRemoval() {
  const removeButton = [...document.querySelectorAll('button')].find(button => button.textContent.trim() === 'Remove employee')
  if (removeButton) removeButton.hidden = selectedEmployeeId() === 'ADM-001'
}

window.addEventListener('click', event => {
  const exportButton = event.target.closest('button')
  if (!exportButton || !exportButton.textContent.includes('Export data')) return
  event.preventDefault()
  event.stopImmediatePropagation()
  const range = window.prompt('Export period: day, week, month, or year', 'day')?.trim().toLowerCase()
  if (!['day', 'week', 'month', 'year'].includes(range)) return
  const dateInput = document.querySelector('input[type="date"]')
  const anchorDate = dateInput?.value || new Date().toISOString().slice(0, 10)
  downloadWorkbook(range, anchorDate).catch(error => window.alert(error.response?.data?.detail || 'Attendance export could not be downloaded.'))
}, true)

const observer = new MutationObserver(syncAdminRemoval)
observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['value'] })
syncAdminRemoval()
