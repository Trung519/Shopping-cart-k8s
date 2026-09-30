import { expect, test } from '@playwright/test'

test.describe('ShopCart marketplace', () => {
  test('renders the current storefront', async ({ page }) => {
    const response = await page.goto('/')

    expect(response?.status()).toBe(200)
    await expect(page.getByRole('heading', { level: 1 })).toContainText('ShopCart Marketplace')
    await expect(page.locator('a[href="/products"]:visible').first()).toBeVisible()
  })

  test('loads the public catalog without API failures', async ({ page }) => {
    const failedResponses: string[] = []
    page.on('response', (response) => {
      if (response.url().includes('/api/v2/products') && response.status() >= 500) {
        failedResponses.push(`${response.status()} ${response.url()}`)
      }
    })

    await page.goto('/products')
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    await expect(page.locator('main').first()).toBeVisible()
    expect(failedResponses).toEqual([])
  })

  test('opens a real product detail when products exist', async ({ page }) => {
    await page.goto('/products')
    const productLink = page.locator('a[href^="/products/"]').first()

    if (await productLink.count()) {
      await productLink.click()
      await expect(page).toHaveURL(/\/products\/[0-9a-f-]+$/)
      await expect(page.locator('main')).toBeVisible()
    }
  })

  test('shows the current secure login screen', async ({ page }) => {
    await page.goto('/login')

    await expect(page.getByRole('heading', { name: /Đăng nhập ShopCart/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /Tiếp tục với tài khoản ShopCart/i })).toBeVisible()
  })

  for (const route of ['/cart', '/checkout', '/orders', '/buyer', '/seller', '/admin']) {
    test(`protects ${route} for anonymous users`, async ({ page }) => {
      await page.goto(route)
      await expect(page).toHaveURL(/\/login$/)
    })
  }

  test('renders the not-found page', async ({ page }) => {
    await page.goto('/route-does-not-exist')
    await expect(page.locator('main')).toBeVisible()
    await expect(page.getByRole('link', { name: /trang chủ|home/i }).first()).toBeVisible()
  })

  test('has no horizontal page overflow', async ({ page }) => {
    await page.goto('/')
    const dimensions = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }))

    expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1)
  })

  test('has one visible primary heading and named interactive controls', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1)

    const unnamed = await page.locator('button:visible, a:visible').evaluateAll((elements) =>
      elements.filter((element) => {
        const label = element.getAttribute('aria-label') || element.textContent?.trim()
        return !label
      }).length,
    )
    expect(unnamed).toBe(0)
  })
})
