const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });

  const shots = [
    ['http://127.0.0.1:5050/', 'home.png', true],
    ['http://127.0.0.1:5050/catalog', 'catalog.png', true],
    ['http://127.0.0.1:5050/catalog?category=bouquets', 'catalog_bouquets.png', true],
    ['http://127.0.0.1:5050/reviews', 'reviews.png', true],
  ];
  const forceReveal = () => {
    document.querySelectorAll('.reveal').forEach(el => el.classList.add('is-visible'));
    // .fade-in relies on a CSS keyframe animation timed from paint; in this sandbox the
    // blocked Google Fonts request can delay first paint unpredictably, so for screenshots
    // (only) force the end state directly instead of waiting on animation timing.
    document.querySelectorAll('.fade-in').forEach(el => {
      el.style.animation = 'none';
      el.style.opacity = '1';
      el.style.transform = 'none';
    });
  };

  for (const [url, file, full] of shots) {
    await page.goto(url, { waitUntil: 'networkidle' });
    await page.waitForTimeout(300);
    await page.evaluate(forceReveal);
    await page.waitForTimeout(700); // let the .6s reveal transition finish before capturing
    await page.screenshot({ path: '/home/claude/amor-flowers/shots/' + file, fullPage: full });
    console.log('shot', file);
  }

  // catalog filters: open both luxe-select dropdowns to check the design
  await page.goto('http://127.0.0.1:5050/catalog?category=bouquets', { waitUntil: 'networkidle' });
  await page.evaluate(forceReveal);
  await page.click('.filter-bar .luxe-select:nth-of-type(1) [data-luxe-trigger]');
  await page.waitForTimeout(150);
  await page.screenshot({ path: '/home/claude/amor-flowers/shots/catalog_filter_open.png' });
  console.log('shot catalog_filter_open.png');

  // apply a flower-type + color filter combo
  await page.check('.filter-bar .luxe-select:nth-of-type(1) input[value="roses"]');
  await page.click('.filter-bar .luxe-select:nth-of-type(1) .luxe-select-apply');
  await page.waitForLoadState('networkidle');
  await page.evaluate(forceReveal);
  await page.waitForTimeout(400);
  await page.screenshot({ path: '/home/claude/amor-flowers/shots/catalog_filtered.png', fullPage: true });
  console.log('shot catalog_filtered.png');

  // header search flyout with live results
  await page.goto('http://127.0.0.1:5050/', { waitUntil: 'networkidle' });
  await page.evaluate(forceReveal);
  await page.click('#search-toggle');
  await page.fill('#search-input', 'букет');
  await page.waitForTimeout(600);
  await page.screenshot({ path: '/home/claude/amor-flowers/shots/search_flyout.png' });
  console.log('shot search_flyout.png');

  // product detail - grab first product link
  await page.goto('http://127.0.0.1:5050/catalog', { waitUntil: 'networkidle' });
  const href = await page.locator('.product-name').first().locator('xpath=..').getAttribute('href');
  await page.goto('http://127.0.0.1:5050' + href, { waitUntil: 'networkidle' });
  await page.evaluate(forceReveal);
  await page.waitForTimeout(700);
  await page.screenshot({ path: '/home/claude/amor-flowers/shots/product.png', fullPage: true });
  console.log('shot product.png', href);

  // add to cart then cart page
  await page.click('#product-add-btn');
  await page.waitForTimeout(300);
  await page.screenshot({ path: '/home/claude/amor-flowers/shots/addon_modal.png' });
  console.log('shot addon_modal.png');
  await page.click('#addon-skip');
  await page.goto('http://127.0.0.1:5050/cart', { waitUntil: 'networkidle' });
  await page.evaluate(forceReveal);
  await page.waitForTimeout(700);
  await page.screenshot({ path: '/home/claude/amor-flowers/shots/cart.png', fullPage: true });
  console.log('shot cart.png');

  await page.goto('http://127.0.0.1:5050/checkout', { waitUntil: 'networkidle' });
  await page.evaluate(forceReveal);
  await page.waitForTimeout(700);
  await page.screenshot({ path: '/home/claude/amor-flowers/shots/checkout.png', fullPage: true });
  console.log('shot checkout.png');

  // language switch to kk
  await page.goto('http://127.0.0.1:5050/set-language/kk', { waitUntil: 'networkidle' });
  await page.goto('http://127.0.0.1:5050/', { waitUntil: 'networkidle' });
  await page.evaluate(forceReveal);
  await page.waitForTimeout(700);
  await page.screenshot({ path: '/home/claude/amor-flowers/shots/home_kk.png', fullPage: false });
  console.log('shot home_kk.png');
  await page.goto('http://127.0.0.1:5050/set-language/ru', { waitUntil: 'networkidle' });

  // admin
  await page.goto('http://127.0.0.1:5050/admin/login', { waitUntil: 'networkidle' });
  await page.fill('input[name=username]', 'admin');
  await page.fill('input[name=password]', 'amor2026');
  await page.click('button[type=submit]');
  await page.waitForTimeout(300);
  await page.screenshot({ path: '/home/claude/amor-flowers/shots/admin_dashboard.png', fullPage: true });
  console.log('shot admin_dashboard.png');

  await page.goto('http://127.0.0.1:5050/admin/products', { waitUntil: 'networkidle' });
  await page.screenshot({ path: '/home/claude/amor-flowers/shots/admin_products.png', fullPage: true });
  console.log('shot admin_products.png');

  await page.goto('http://127.0.0.1:5050/admin/products/new', { waitUntil: 'networkidle' });
  await page.screenshot({ path: '/home/claude/amor-flowers/shots/admin_product_new.png', fullPage: true });
  console.log('shot admin_product_new.png');

  await browser.close();
})();
