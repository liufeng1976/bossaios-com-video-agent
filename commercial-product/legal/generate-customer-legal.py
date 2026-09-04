from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

PRODUCT_ID = "bossai-video-agent"
PRODUCT_NAME = "BossAI Video Agent"
REQUIRED_TEXT = (
    "approvedBy",
    "approvedAt",
    "legalEntityName",
    "registeredAddress",
    "supportEmail",
    "privacyContact",
    "governingLaw",
    "disputeVenue",
    "refundPolicy",
    "supportHours",
    "dataRetentionSummary",
    "termsEffectiveDate",
)


def load_config(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "bossai.video-agent-legal-config.v1":
        raise RuntimeError("unsupported legal config schema")
    if data.get("productId") != PRODUCT_ID:
        raise RuntimeError("legal config belongs to another product")
    if data.get("approved") is not True:
        raise RuntimeError("legal config is not approved for customer release")
    missing = [key for key in REQUIRED_TEXT if not str(data.get(key) or "").strip()]
    if not data.get("salesTerritories"):
        missing.append("salesTerritories")
    if not data.get("cloudProcessingRegions"):
        missing.append("cloudProcessingRegions")
    if missing:
        raise RuntimeError("legal config is incomplete: " + ", ".join(missing))
    return data


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_terms(c: dict) -> str:
    return f"""# {PRODUCT_NAME} 客户服务条款\n\n生效日期：{c['termsEffectiveDate']}\n\n服务提供方：{c['legalEntityName']}\n注册地址：{c['registeredAddress']}\n销售地区：{', '.join(c['salesTerritories'])}\n支持邮箱：{c['supportEmail']}\n支持电话：{c.get('supportPhone') or '以订单或支持页面公布为准'}\n\n## 1. 产品与服务\n\n{PRODUCT_NAME} 是面向内容生产的 Windows 桌面软件。实际可用能力以客户套餐、设备授权、已安装运行组件和产品界面为准。\n\n## 2. Freemium 套餐与商业用途\n\nFree Personal 为个人用途永久免费基础额度；Personal Pro 为个人订阅高额度；Business 才授权公司生产、客户交付、收费服务、营销经营等商业用途。账号、订阅、License、BossAI Points、Quota、Device Binding 和 Entitlement 均由 BossAI 现有商业权威管理，本产品不得另建本地收费权威。历史上已按 MIT 发布的旧版本授权继续有效；当前 BossAI 自有源码按 BossAI Community Source License 公开，个人/非商业用途免费，商业用途必须通过 BossAI Commercial License / Headquarters entitlement 授权。授权或套餐变化不得删除客户已经生成的本地资料。\n\n## 3. 素材和人格权授权\n\n客户必须对声音、肖像、人物视频、商标、音乐、文字、图片及其他素材拥有足够的商业使用权。禁止未经同意的声音克隆、肖像仿冒、冒充他人、侵权营销或违法内容制作。\n\n## 4. AI 输出与发布责任\n\nAI 输出可能存在事实、表达、合规和平台规则风险。客户在公开发布前应自行审核内容、价格、承诺、资质、广告表述和知识产权状态。\n\n## 5. 第三方组件\n\n部分本地能力依赖独立第三方开源代码或模型。相应组件继续适用其自身许可证、模型卡和使用条款，BossAI 不重新授予第三方权利。\n\n## 6. 平台发布\n\n平台发布仅在产品明确启用且完成对应真实账号验收时属于交付范围。客户必须遵守目标平台的账号、内容、自动化和发布规则。\n\n## 7. 付款、退款和支持\n\n退款规则：{c['refundPolicy']}\n\n支持时间：{c['supportHours']}\n\n## 8. 法律与争议\n\n适用法律：{c['governingLaw']}\n\n争议解决地点/机构：{c['disputeVenue']}\n\n本文件由 {c['approvedBy']} 于 {c['approvedAt']} 批准进入客户发行包。\n"""


def render_privacy(c: dict) -> str:
    return f"""# {PRODUCT_NAME} 隐私说明\n\n生效日期：{c['termsEffectiveDate']}\n\n数据处理主体：{c['legalEntityName']}\n隐私联系渠道：{c['privacyContact']}\n\n## 本地优先\n\n客户上传的声音、人物视频、生成音频、生成视频和项目资料默认保存在客户设备，除非客户主动选择明确标注的云端能力。\n\n## 可能发送给 BossAI 服务的数据\n\n统一账号所需的账号标识和验证数据；产品 ID、版本和非秘密设备标识；套餐、商业授权、积分和结算所需的最小商业信息；以及客户主动提交给已启用云端 AI 功能的任务内容。\n\n密码、验证码、客户本地 Provider Key 不属于商业授权快照，不应上传为授权状态。\n\n## 声音与人物素材\n\n声音和人物素材可能涉及肖像、声音权益或其他敏感权益。客户应确保具有合法依据和必要授权，并可在本地删除授权素材及成果。\n\n## 数据保留\n\n{c['dataRetentionSummary']}\n\n## 云端处理区域\n\n{', '.join(c['cloudProcessingRegions'])}\n\n## 第三方服务\n\n内容平台、模型服务和第三方组件可能适用独立隐私政策；只有在启用相应功能时才发生对应数据流。\n"""


def render_authorization(c: dict) -> str:
    return f"""# {PRODUCT_NAME} 声音与人物素材授权确认\n\n客户在使用声音合成或数字人口播前确认：\n\n1. 素材属于本人/本单位，或已取得覆盖商业 AI 合成用途的明确授权；\n2. 授权覆盖必要的音频处理、声音合成、口型同步、视频生成和约定渠道传播；\n3. 不使用未经同意的公众人物、员工、客户、未成年人或其他第三方素材进行冒充、误导或侵权传播；\n4. 不绕过产品中的授权确认；\n5. 对最终发布内容承担发布前审核责任。\n\n支持与授权争议联系：{c['supportEmail']}\n"""


def render_support(c: dict) -> str:
    return f"""# {PRODUCT_NAME} 安装与支持说明\n\n服务提供方：{c['legalEntityName']}\n支持邮箱：{c['supportEmail']}\n支持电话：{c.get('supportPhone') or '以订单或支持页面公布为准'}\n支持时间：{c['supportHours']}\n\n## 安装形态\n\n产品提供 Windows 桌面客户端。大型 AI runtime 可在首次使用时从固定、可追溯来源安装；未知来源 runtime 不自动启用。\n\n## 客户环境\n\n显卡驱动、磁盘、内存和网络要求以对应版本的安装检查页为准。第三方模型仓库和内容平台可能变化，BossAI 提供兼容说明和升级路径，但不承诺第三方服务永久不变。\n\n## 退款和迁移\n\n{c['refundPolicy']}\n\n## 数据与迁移\n\n业务数据默认保存在客户本地。授权失效不得删除客户已经生成的本地业务资料；迁移、备份和售后范围以订单或补充协议为准。\n"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate approved BossAI Video Agent customer legal documents.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    config = load_config(Path(args.config).expanduser().resolve())
    out = Path(args.out).expanduser().resolve()
    if out.exists() and any(out.iterdir()) and not args.replace:
        raise RuntimeError(f"legal output is not empty: {out}")
    out.mkdir(parents=True, exist_ok=True)

    rendered = {
        "CUSTOMER_TERMS.md": render_terms(config),
        "PRIVACY_NOTICE.md": render_privacy(config),
        "VOICE_AVATAR_AUTHORIZATION.md": render_authorization(config),
        "SUPPORT_AND_INSTALLATION.md": render_support(config),
    }
    for name, content in rendered.items():
        (out / name).write_text(content, encoding="utf-8")

    files = [{"path": name, "sha256": sha256(out / name)} for name in sorted(rendered)]
    manifest = {
        "schema": "bossai.video-agent-legal-release.v1",
        "productId": PRODUCT_ID,
        "approved": True,
        "approvedBy": config["approvedBy"],
        "approvedAt": config["approvedAt"],
        "effectiveDate": config["termsEffectiveDate"],
        "legalEntityName": config["legalEntityName"],
        "supportEmail": config["supportEmail"],
        "privacyContact": config["privacyContact"],
        "files": files,
    }
    (out / "legal-release-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "files": len(files), "out": str(out)}, ensure_ascii=False, indent=2))
    print("RESULT: approved BossAI customer legal bundle generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
