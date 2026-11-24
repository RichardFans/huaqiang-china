/** 站点基础路径与仓库地址（项目页部署在 /huaqiang-china 之下，站内链接一律经 withBase）。 */
const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');

export const withBase = (path: string): string => `${BASE}${path}`;

export const REPO = 'https://github.com/RichardFans/huaqiang-china';
export const repoBlob = (path: string): string => `${REPO}/blob/main/${path}`;
export const repoIssue = (template: string): string => `${REPO}/issues/new?template=${template}`;
