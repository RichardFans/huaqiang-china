import { defineConfig } from 'astro/config';

// 站点部署假设：GitHub Pages 根域（org/repo = huaqiang-china）
// 实际仓库位置确定后，需同步改这里与 tools/zfq/build.py 的 SITE_URL（见 README 部署节）
export default defineConfig({
  site: 'https://huaqiang-china.github.io',
  base: '/',
  trailingSlash: 'ignore',
});
