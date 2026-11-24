/** 数值与日期格式化：全站只在这里定义，避免各页各写一套。 */
const nf = new Intl.NumberFormat('en-US');

/** 千分位整数；空值返回空串（由调用处决定占位文案）。 */
export const fmt = (n?: number | null): string => (n == null ? '' : nf.format(n));

/** 中文读者习惯的计数：1.2亿 / 5117.7万 / 9,865（B 站播放量的惯用读法）。 */
export const fmtCn = (n?: number | null): string => {
  if (n == null) return '';
  if (n >= 1e8) {
    const v = n / 1e8;
    return `${v.toFixed(v >= 10 ? 1 : 2).replace(/\.?0+$/, '')}亿`;
  }
  if (n >= 1e4) return `${(n / 1e4).toFixed(1).replace(/\.0$/, '')}万`;
  return nf.format(n);
};

/** 播放/硬币等计数：中文页用万亿读法，英文页用千分位。 */
export const fmtCount = (en: boolean, n?: number | null): string => (en ? fmt(n) : fmtCn(n));

export const fmtDate = (iso?: string | null): string => (iso ? iso.slice(0, 10) : '');
