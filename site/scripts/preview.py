# -*- coding: utf-8 -*-
"""站点本地预览：按站点的 base 路径（/huaqiang-china）伺服 site/dist，仅绑定 127.0.0.1。

用法（在仓库根目录）：
    python site/scripts/preview.py 8686
然后打开 http://127.0.0.1:8686/huaqiang-china/

为什么不用 `astro preview`：它会占用 astro 的默认端口，与本机端口台账冲突；
8686 是本项目在台账里登记的预览端口。
"""
import functools
import http.server
import socketserver
import sys

ROOT = "site/dist"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8686
BASE = "/huaqiang-china"


class Handler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        p = path.split("?", 1)[0].split("#", 1)[0]
        if p == BASE:
            p = "/"
        elif p.startswith(BASE + "/"):
            p = p[len(BASE):]
        return super().translate_path(p)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(
            ("127.0.0.1", PORT), functools.partial(Handler, directory=ROOT)) as srv:
        print(f"preview ready: http://127.0.0.1:{PORT}{BASE}/  (Ctrl+C 停止)", flush=True)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
