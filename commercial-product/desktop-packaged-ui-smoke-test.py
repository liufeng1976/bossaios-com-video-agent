from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

sys.dont_write_bytecode = True


def wait_port(host: str, port: int, timeout: float) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.35)
            try:
                sock.connect((host, port))
                return
            except OSError:
                time.sleep(0.2)
    raise RuntimeError(f"port did not become ready: {host}:{port}")


def fetch_json(url: str, timeout: float = 3.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((host, port)) != 0


async def run(args: argparse.Namespace) -> dict:
    site_packages = pathlib.Path(args.site_packages).resolve()
    if str(site_packages) not in sys.path:
        sys.path.insert(0, str(site_packages))
    from patchright.async_api import async_playwright

    app_exe = pathlib.Path(args.app_exe).resolve()
    if not app_exe.is_file():
        raise RuntimeError(f"packaged BossAI application missing: {app_exe}")

    api_port = args.api_port
    cdp_port = args.cdp_port
    if not port_is_free("127.0.0.1", api_port):
        raise RuntimeError(f"business API port already occupied: {api_port}")
    if not port_is_free("127.0.0.1", cdp_port):
        raise RuntimeError(f"CDP port already occupied: {cdp_port}")

    temp_root = pathlib.Path(tempfile.mkdtemp(prefix="bossai-video-packaged-smoke-"))
    local_appdata = temp_root / "LocalAppData"
    local_appdata.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "LOCALAPPDATA": str(local_appdata),
            "BOSSAI_VIDEO_PORT": str(api_port),
            "ELECTRON_ENABLE_LOGGING": "1",
            "BOSSAI_VIDEO_DIAGNOSTICS": "1",
        }
    )
    env.pop("ELECTRON_RUN_AS_NODE", None)

    started = time.perf_counter()
    process: subprocess.Popen[str] | None = None
    stdout_handle = None
    stderr_handle = None
    stdout_path = temp_root / "electron.stdout.log"
    stderr_path = temp_root / "electron.stderr.log"
    browser = None
    result: dict[str, object] = {}
    try:
        stdout_handle = stdout_path.open("w", encoding="utf-8", errors="replace")
        stderr_handle = stderr_path.open("w", encoding="utf-8", errors="replace")
        process = subprocess.Popen(
            [str(app_exe), f"--remote-debugging-port={cdp_port}", "--remote-allow-origins=*"],
            cwd=str(app_exe.parent),
            env=env,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
        )
        wait_port("127.0.0.1", cdp_port, 25.0)
        wait_port("127.0.0.1", api_port, 45.0)

        health = fetch_json(f"http://127.0.0.1:{api_port}/health")
        if health.get("success") is not True or (health.get("data") or {}).get("product") != "bossai-video-agent":
            raise AssertionError(f"unexpected packaged backend health: {health}")

        async with async_playwright() as playwright:
            browser = await playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}")
            contexts = browser.contexts
            if not contexts:
                raise AssertionError("packaged Electron exposed no CDP browser context")
            context = contexts[0]
            deadline = time.time() + 20.0
            page = None
            while time.time() < deadline:
                for candidate in list(context.pages):
                    try:
                        if not candidate.is_closed() and candidate.url.startswith("file:"):
                            page = candidate
                            break
                    except Exception:
                        continue
                if page is not None:
                    break
                await asyncio.sleep(0.2)
            if page is None:
                raise AssertionError("BossAI packaged renderer page did not become available")

            await page.wait_for_load_state("domcontentloaded", timeout=15000)
            title = await page.title()
            body = await page.locator("body").inner_text()
            if "BossAI Video Agent" not in body:
                raise AssertionError("BossAI product identity is not visible in packaged UI")
            if "经营首页" not in body or "AI 口播视频" not in body or "关于与合规" not in body:
                raise AssertionError("packaged BossAI navigation is incomplete")

            legacy_literals = [
                "".join(chr(v) for v in (0x5CB3, 0x54E5)),
                "".join(chr(v) for v in (0x41, 0x49, 0x667A, 0x80FD, 0x4F53)),
                "".join(chr(v) for v in (0x41, 0x49, 0x41, 0x67, 0x65, 0x6E, 0x74)),
            ]
            visible_legacy = [marker for marker in legacy_literals if marker and marker in body]
            if visible_legacy:
                raise AssertionError("legacy identity is visible in packaged commercial UI")

            # Do not inspect contextBridge globals through CDP page.evaluate().
            # Electron 39 exposes the bridge to the renderer main world used by
            # the Vue application, while Playwright's attached CDP execution
            # context can observe a different world. Validate the bridge through
            # actual customer-visible UI state instead.
            if "运行环境安装只允许从 BossAI Video Agent 桌面应用发起" in body:
                raise AssertionError("packaged Vue renderer did not receive the BossAI desktop runtime-control bridge")

            publish_status = fetch_json(f"http://127.0.0.1:{api_port}/api/commercial/publish/status")
            publish_data = publish_status.get("data") or {}
            if publish_status.get("success") is not True or publish_data.get("automatedPublishAllowed") is not False:
                raise AssertionError(f"commercial publish gate is not fail-closed: {publish_status}")
            if publish_data.get("manualExportAllowed") is not True or publish_data.get("approvalRequired") is not True:
                raise AssertionError(f"commercial publish/export policy is incomplete: {publish_status}")

            await page.get_by_role("button", name="AI 口播视频", exact=True).click()
            await page.get_by_text("自动发布尚未开放", exact=True).wait_for(timeout=5000)
            studio_body = await page.locator("body").inner_text()
            for expected in ("01\n定义内容", "02\n使用已授权声音生成配音", "03\n授权数字人口播", "04\n生成成片并导出", "05\n发布"):
                if expected not in studio_body:
                    raise AssertionError(f"commercial workflow screen missing step: {expected}")
            if "自动发布尚未开放" not in studio_body:
                raise AssertionError("commercial publish fail-closed state is not visible in packaged UI")
            publish_mode = await page.locator('label').filter(has_text='当前发布模式').locator('input').input_value()
            if publish_mode != '本地导出 + 人工发布':
                raise AssertionError(f"unexpected packaged publish mode: {publish_mode!r}")
            if "文件导出仅在 BossAI Video Agent 桌面应用中启用" in studio_body:
                raise AssertionError("packaged Vue renderer did not receive the BossAI final-video export bridge")

            await page.get_by_role("button", name="关于与合规", exact=True).click()
            await page.get_by_text("客户法律包尚未批准", exact=True).wait_for(timeout=5000)
            legal_body = await page.locator("body").inner_text()
            for expected in ("客户服务条款", "隐私说明", "声音与人物素材授权确认", "安装与支持说明", "第三方组件说明"):
                if expected not in legal_body:
                    raise AssertionError(f"legal/compliance screen missing item: {expected}")
            notices_row = page.locator('.runtime-row').filter(has_text='第三方组件说明')
            terms_row = page.locator('.runtime-row').filter(has_text='客户服务条款')
            if '可查看' not in await notices_row.inner_text():
                raise AssertionError('third-party notice availability did not reach the Vue renderer through the desktop bridge')
            if not await notices_row.get_by_role('button', name='打开').is_enabled():
                raise AssertionError('third-party notice open action is not enabled in packaged desktop UI')
            if '未进入发行包' not in await terms_row.inner_text():
                raise AssertionError('unapproved customer terms were not kept fail-closed in packaged desktop UI')

            result = {
                "status": "passed",
                "productId": "bossai-video-agent",
                "productName": "BossAI Video Agent",
                "windowTitle": title,
                "backendHealthPassed": True,
                "legalBridgePassed": True,
                "approvedLegalBundlePresent": False,
                "thirdPartyNoticesAvailable": True,
                "legacyVisibleIdentityMatches": 0,
                "commercialWorkflowReached": True,
                "finalVideoExportBridgePassed": True,
                "publishFailClosedPassed": True,
                "legalScreenReached": True,
            }

            await page.evaluate("() => window.close()")
            await asyncio.sleep(0.8)
            await browser.close()
            browser = None

        if process is not None:
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=8)
        deadline = time.time() + 12.0
        while time.time() < deadline and not port_is_free("127.0.0.1", api_port):
            time.sleep(0.25)
        if not port_is_free("127.0.0.1", api_port):
            raise AssertionError("packaged BossAI backend port remained occupied after UI exit")

        result["backendPortReleased"] = True
        result["elapsedSeconds"] = round(time.perf_counter() - started, 3)
        return result
    finally:
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if stdout_handle is not None:
            stdout_handle.close()
        if stderr_handle is not None:
            stderr_handle.close()
        shutil.rmtree(temp_root, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke the independently packaged BossAI Video Agent desktop UI and legal bridge.")
    parser.add_argument("--app-exe", required=True)
    parser.add_argument("--site-packages", required=True)
    parser.add_argument("--api-port", type=int, default=8765)
    parser.add_argument("--cdp-port", type=int, default=9337)
    args = parser.parse_args()
    result = asyncio.run(run(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("RESULT: packaged BossAI Video Agent desktop/legal smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
