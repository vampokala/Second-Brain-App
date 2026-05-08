import { test, expect } from '@playwright/test'

test.describe('chat tab', () => {
  test('shows Chat heading', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Chat' })).toBeVisible()
  })
})
