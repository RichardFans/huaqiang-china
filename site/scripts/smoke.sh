#!/usr/bin/env bash
# 部署后冒烟检查（由 .github/workflows/ci.yml 的 deploy-smoke 调用，也可本地运行）。
#
# 用法：bash site/scripts/smoke.sh https://richardfans.github.io/huaqiang-china/
#
# 2026-11-24 教训：站点曾“在线但整页没有样式”，而 HTML 与 CSS 文件都返回 200，
# 只查资源可达发现不了。这里不查渲染，只守住底线：
#   1. 关键页面可达；
#   2. 首页引用的每一份样式表、脚本都可达；
#   3. 样式表非空。
# “样式是否真的作用于页面”由构建后的 site/scripts/assert-global-css.mjs 把关。
set -euo pipefail

URL="${1:?用法: smoke.sh <站点地址>}"
URL="${URL%/}"                                              # 地址带不带尾斜杠都可以
ORIGIN=$(printf '%s' "$URL" | sed -E 's#^(https?://[^/]+).*#\1#')

code_of() { curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$1"; }

expect_200() {
  local url="$1" label="$2" code
  for i in 1 2 3 4 5 6; do                                  # Pages 刚部署完可能还没就绪
    code=$(code_of "$url")
    if [ "$code" = "200" ]; then echo "OK   $label $url"; return 0; fi
    echo "wait $code $url ($i/6)"; sleep 10
  done
  echo "FAIL $label $url -> $code"; return 1
}

# 站内资源是相对域名的绝对路径（已含 /huaqiang-china 前缀），要拼在域名后面
abs() {
  case "$1" in
    http*) printf '%s' "$1" ;;
    /*) printf '%s%s' "$ORIGIN" "$1" ;;
    *) printf '%s/%s' "$URL" "$1" ;;
  esac
}

for path in / /graph/ /charts/ /chronicle/ /creators/ /scene/maigua/ /en/ /graph.gexf; do
  expect_200 "${URL}${path}" "page"
done

html=$(curl -fsSL --max-time 30 "${URL}/")
refs=$(printf '%s' "$html" | grep -oE '(href|src)="[^"]+\.(css|js)"' \
  | sed -E 's/^(href|src)="//; s/"$//' | sort -u)
test -n "$refs"
for r in $refs; do expect_200 "$(abs "$r")" "asset"; done

css=$(printf '%s' "$refs" | grep '\.css$' | head -n 1)
test -n "$css"
bytes=$(curl -s --max-time 30 "$(abs "$css")" | wc -c)
echo "stylesheet bytes: $bytes"
[ "$bytes" -gt 1000 ]
