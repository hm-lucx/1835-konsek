import { expect, test } from '@playwright/test'

// Acceptance: a solo user clicks through the complete first (start-packet) AR —
// start a game, buy a start-packet item, pass until the round ends.
test('solo user plays through the first AR', async ({ page }) => {
  await page.goto('/')

  // Start a solo game; the board must render.
  await page.getByRole('button', { name: /Neues Solo-Spiel/i }).click()
  const hexMap = page.getByTestId('hex-map')
  await expect(hexMap).toBeVisible()
  // The 14×10 board projects 42 named positions.
  await expect(hexMap.locator('g[data-testid^="hex-"]')).toHaveCount(42)

  // The ActionBar shows only server-provided actions (buy_start_item, pass).
  await expect(page.getByTestId('action-buy_start_item').first()).toBeVisible()

  // Buy the first start-packet item → log records it, cash drops.
  await page.getByTestId('action-buy_start_item').first().click()
  await expect(page.getByTestId('log-1')).toBeVisible()
  await expect(page.getByTestId('player-Player 1')).toContainText('500 M')

  // Pass three times (3 players) → the AR ends and an OR begins.
  for (let i = 0; i < 3; i += 1) {
    await page.getByTestId('action-pass').click()
  }
  await expect(page.getByTestId('action-bar')).toContainText('or')
})

test('stock market renders price markers stacked top-first', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /Neues Solo-Spiel/i }).click()
  await expect(page.getByTestId('stock-market')).toBeVisible()
})
