# BossAI First-Party Assets / BossAI 自有素材

## 中文

这个目录用于随产品分发 **BossAI 自己拥有或已取得商业再分发授权** 的素材：音色、人物视频、画中画素材、背景音乐。

产品默认**不携带任何素材**，`manifest.json` 的 `assets` 是空的。这是正确的初始状态，不是缺陷。

### 为什么不能直接放原版素材

`runtime-license-inventory.json` 里已经把复原包里的素材标记为：

```
legacy-bgm-library            blocked-do-not-distribute
legacy-digital-human-engine   blocked-do-not-distribute
```

理由是「未找到逐条商业再分发证据」。`PUBLIC_REPOSITORY_POLICY.md` 也明确禁止「权利不明确的模型权重、声音、人物、音乐、字体、图片或其他资产」。

把这些素材放进来，等于用一个新目录绕开既有结论。**不要这样做。**

### 添加一个素材

1. 把文件放进 `voices/`、`avatars/`、`media/` 或 `bgm/`；
2. 计算 SHA-256：`(Get-FileHash <file> -Algorithm SHA256).Hash.ToLower()`；
3. 在 `manifest.json` 的 `assets` 里加一条，所有字段都必填：

```json
{
  "id": "bossai-brand-voice-01",
  "kind": "voice",
  "file": "voices/bossai-brand-voice-01.wav",
  "displayName": "BossAI 品牌音色 01",
  "sha256": "<64 位小写十六进制>",
  "rightsHolder": "BossAI",
  "license": "BossAI-owned; full commercial redistribution rights",
  "acquisitionRecord": "合同/发票/录制授权书的可核查编号",
  "sourceType": "bossai-owned"
}
```

4. 填写 `reviewedBy` 与 `reviewedAt`；
5. 运行 `python commercial-product/verify-first-party-assets.py`。

任何一条缺字段、哈希不符、文件缺失或 `sourceType` 不在允许列表内，校验都会失败，且 GA 门禁会随之 fail-closed。

`sourceType` 允许值：

- `bossai-owned` —— BossAI 自行录制/制作，完全自有；
- `licensed-for-redistribution` —— 第三方授权，且合同明确允许随产品再分发。

仅仅「购买了使用权」不等于「可随产品再分发」。拿不准就不要加。

## English

This directory ships assets that BossAI **owns outright or holds a documented
commercial redistribution licence for**: voices, avatar clips, picture-in-picture
media and background music.

The product ships **no assets by default** — an empty `assets` array is the
correct initial state, not a gap.

Assets recovered from the original AIAgent package are recorded as
`blocked-do-not-distribute` in `runtime-license-inventory.json` because no
per-item commercial redistribution evidence was found. Adding them here would
route around that finding. Do not.

To add one: drop the file into `voices/`, `avatars/`, `media/` or `bgm/`, record
its SHA-256, add a fully populated entry to `manifest.json`, fill in `reviewedBy`
and `reviewedAt`, then run `verify-first-party-assets.py`. A missing field, a
hash mismatch, a missing file or an unrecognised `sourceType` fails the check and
the GA gate with it.

A licence to *use* an asset is not a licence to *redistribute* it inside a
product. When in doubt, leave it out.
