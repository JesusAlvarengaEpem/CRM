const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ 
    headless: true,
    executablePath: 'C:\\Users\\jesus.alvarenga\\AppData\\Local\\ms-playwright\\chromium-1208\\chrome-win64\\chrome.exe'
  });
  const page = await browser.newPage();

  // Capture console errors
  const errors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });

  try {
    // 1. Login
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
    await page.fill('input[type="email"]', 'admin@epem.com');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    console.log('✅ Login OK');

    // 2. Go to Supervisores
    await page.goto('http://localhost:3000/dashboard/supervisores', { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);
    console.log('✅ Supervisores page loaded');

    // 3. Check table rows
    const rows = await page.$$('table tbody tr');
    console.log(`   Table rows: ${rows.length}`);

    if (rows.length > 0) {
      const firstRowText = await rows[0].textContent();
      console.log(`   First row: "${firstRowText.trim()}"`);

      // 4. Click first row
      await rows[0].click();
      await page.waitForTimeout(3000);

      // 5. Check for drilldown panel
      const h2 = await page.$('h2');
      if (h2) {
        const h2Text = await h2.textContent();
        console.log(`   H2 found: "${h2Text}"`);
      }

      const drillPanel = await page.$('div.border-l-2');
      if (drillPanel) {
        console.log('✅ Drilldown panel appeared');
        const sellerRows = await page.$$('div.border-l-2 tbody tr');
        console.log(`   Seller rows in drilldown: ${sellerRows.length}`);
      } else {
        console.log('❌ No drilldown panel (no div.border-l-2)');
      }

      // Check for error text
      const errEl = await page.$('.text-warning-red');
      if (errEl) {
        const errText = await errEl.textContent();
        console.log(`   Error displayed: "${errText}"`);
      }

    } else {
      console.log('❌ No table rows - data not loaded');
    }

    if (errors.length > 0) {
      console.log(`   Browser console errors: ${errors.join(' | ')}`);
    }

  } catch (err) {
    console.log(`❌ Exception: ${err.message}`);
  } finally {
    await browser.close();
  }
})();
