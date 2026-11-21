# 🍉 The Conquest Remix Archive · 征服二创宇宙档案

> An open, reproducible research archive that **collects, organizes and tracks** the
> derivative-work universe around *The Conquest* (《征服》, 2003) — the TV drama behind
> one of China's most beloved internet memes: **Liu Huaqiang buying a watermelon**
> (“你这瓜保熟吗？” — “Is this melon *guaranteed ripe*?”).
> **中文 → [README.md](README.md)** ｜ 🌐 Site: `huaqiang-china.github.io`

<!-- zfq:generated:start -->
<!-- zfq:generated:end -->

## A very short cultural guide

- **保熟 (bǎo shú), “guaranteed ripe”** — In the founding scene, gangster Liu Huaqiang
  questions a melon vendor's guarantee, then escalates the transaction into a knife.
  The line became a nationwide shorthand for any suspicious promise.
- **鬼畜 (guichu)** — Bilibili-native remix genre: rhythmically re-cut footage with
  pitch-shifted audio, descended from Japanese 音MAD. Highly crafted, often musical.
- **AI 翻唱 (AI cover)** — Since ~2023, voice cloning (so-vits-svc / RVC) let creators
  make Liu Huaqiang *sing* anything. The meme industrialized: same scene, new throat.
- Titles are shown in the original Chinese; every number is a **timestamped first-hand
  snapshot** from public endpoints, cross-validated across two independent surfaces.
  Auto-catalogued entries are marked ⚠ (*pending human review*) — we show uncertainty
  instead of hiding it.

## 📡 Subscribe (feeds)

- New entries RSS (EN) `/feeds/new.en.rss.xml` ｜ 新收录 RSS（中文）`/feeds/new.rss.xml`
- Weekly movers `/feeds/movers.rss.xml` ｜ Atom `/feeds/atom.xml` ｜ JSON Feed `/feeds/feed.json`
- Full faceted lists (scene / creator / tier): [docs/lists/](docs/lists/) — auto-generated.

## 🚀 Quick start

```bash
python -m pip install requests pydantic jsonschema pytest
export PYTHONPATH=tools
python -m zfq.validate    # data gates R1–R7 (offline)
python -m pytest -q       # tests
python -m zfq.track       # tracking refresh (online, rate-limited 1 req/s)
python -m zfq.build       # rebuild views / lists / README / feeds / site data
```

Site (local): `cd site && npm install && npm run build` → `site/dist/` (fully static).

## 🗂 Governance

- Corpus boundary & inclusion thresholds: [ADR-0001](docs/decisions/0001-scope-and-inclusion.md)
- Collection legal posture (browser-equivalent, metadata-only, rate-limited, takedown
  channel honored within 72h): [ADR-0002](docs/decisions/0002-collection-legal-posture.md)
- Review gate — auto-catalogued ≠ confirmed ([ADR-0006](docs/decisions/0006-review-gate.md))
- Staging methodology (pre-registered) & verification protocol:
  [methodology](docs/methodology.md) · [verification](docs/verification.md)
- All ranking tables in this README are **generated from data** by `zfq build`;
  CI rule R7 blocks any commit where README and data drift apart.

## 🤖 Automation

GitHub Actions: `ci` (gates + site build) · `track` (daily snapshot → auto PR) ·
`discover` (weekly discovery → review PR) · `issue-bot` (submit-video issue → live
validation → PR).

## 📄 License

Code: MIT · Content & data: [CC BY-SA 4.0](LICENSE.content).
Copyright of the videos themselves remains with the original rights holders and
creators; this repository stores metadata and links only — never audio/video bytes.
