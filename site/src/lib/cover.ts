/**
 * 封面地址（ADR-0007）。
 *
 * entries.cover 保存的是快照里的一手原图地址（一律 http、原分辨率、比例不一）。
 * 站点呈现层在这里派生规格化地址：
 *   - 升级为 https（https 页面不再有混合内容）；
 *   - 用图床的等比缩放参数 `@{w}w_{h}h.webp`：完整封面缩进 16:9 框内、不裁切
 *     （带 1c 的裁切参数会把 4:3 封面底部的标题字幕切掉，实测否决），
 *     体积也从几十万字节级降到一两万字节级；
 *   - 解析不了的形态原样放行，加载失败时回退到原图，再失败则显示占位。
 */
const RE = /^(?:https?:)?\/\/(i\d\.hdslb\.com\/[^@?#]+?\.(?:jpe?g|png|gif|webp))(?:@[^?#]*)?(?:[?#].*)?$/i;

function base(cover?: string | null): string | null {
  if (!cover) return null;
  const m = RE.exec(cover.trim());
  if (m) return `https://${m[1]}`;
  return cover.startsWith('//') ? `https:${cover}` : null;
}

/** 规格化封面；cover 为空或形态未知时返回 null。 */
export function coverSrc(cover?: string | null, w = 480, h = 270): string | null {
  const b = base(cover);
  return b ? `${b}@${w}w_${h}h.webp` : null;
}

/** 1x / 2x 两档，供 srcset。 */
export function coverSrcset(cover?: string | null): string | null {
  const b = base(cover);
  return b ? `${b}@480w_270h.webp 480w, ${b}@960w_540h.webp 960w` : null;
}

/** 加载失败时的回退地址（https 原图）。 */
export function coverFallback(cover?: string | null): string | null {
  return base(cover);
}
