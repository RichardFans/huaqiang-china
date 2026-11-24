import { defineConfig } from 'astro/config';

// 站点部署：GitHub Pages 项目页（RichardFans/huaqiang-china）
// 改地址时需与 tools/zfq/build.py 的 SITE_URL 同步，并重跑 zfq build（见 CONTRIBUTING.md）
export default defineConfig({
  site: 'https://richardfans.github.io',
  base: '/huaqiang-china',
  trailingSlash: 'ignore',
});
