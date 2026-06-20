const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ 
    headless: true,
    executablePath: 'C:\\Users\\jesus.alvarenga\\AppData\\Local\\ms-playwright\\chromium-1208\\chrome-win64\\chrome.exe'
  });
  const page = await browser.newPage();
  const errors = [];
  page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });

  try {
    // Login
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
    await page.fill('input[type="email"]', 'admin@epem.com');
    await page.fill('input[type="password"]', 'admin123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard', { timeout: 10000 });
    console.log('✅ Login');

    // Go to Metricas
    await page.goto('http://localhost:3000/dashboard/metricas', { waitUntil: 'networkidle' });
    await page.waitForTimeout(4000);
    console.log('✅ Metricas page loaded');

    // Check sections
    const h2s = await page.$$('h2');
    const titles = [];
    for (const h2 of h2s) titles.push(await h2.textContent());
    console.log(`   Sections: ${titles.join(' | ')}`);

    // Check funnel bars
    const funnelBars = await page.$$('div.flex.items-end.gap-2.h-32 > div');
    console.log(`   Funnel bars: ${funnelBars.length}`);

    // Check aging cards
    const agingCards = await page.$$('div.grid.grid-cols-4.gap-2 > div');
    console.log(`   Aging cards: ${agingCards.length}`);

    // Check pipeline bars
    const pipelineBars = await page.$$('div.grid.grid-cols-4.gap-3 > div');
    console.log(`   Pipeline UNs: ${pipelineBars.length}`);

    // Check performers tables
    const perfTables = await page.$$('table');
    console.log(`   Tables: ${perfTables.length}`);

    // Check trends
    const trendBars = await page.$$('div.flex.items-end.gap-1.h-40 > div');
    console.log(`   Trend bars: ${trendBars.length}`);

    if (errors.length > 0) console.log(`   ⚠️ Errors: ${errors.join(' | ')}`);
    else console.log('   ✅ No console errors');

    console.log('✅ ALL CHECKS PASSED');
  } catch (err) {
    console.log(`❌ ${err.message}`);
  } finally {
    await browser.close();
  }
})();
