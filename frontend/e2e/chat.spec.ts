import { test, expect } from '@playwright/test'

test.describe('chat tab', () => {
  test('shows Chat toggle in the top bar', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('tab', { name: 'Chat' })).toBeVisible()
  })
})
