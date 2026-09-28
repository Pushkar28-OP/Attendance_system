function selectedEmployeeId() {
  const editor = [...document.querySelectorAll('section')].find(section => section.textContent.includes('PEOPLE / EDIT RECORD'))
  return editor?.querySelector('input')?.value || ''
}

function syncAdminRemoval() {
  const removeButton = [...document.querySelectorAll('button')].find(button => button.textContent.trim() === 'Remove employee')
  if (removeButton) removeButton.hidden = selectedEmployeeId() === 'ADM-001'
}

const observer = new MutationObserver(syncAdminRemoval)
observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['value'] })
syncAdminRemoval()
