from __future__ import annotations

import json
import os
import pathlib
import tempfile

import cosyvoice_adapter


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="bossai-cosy-env-") as raw:
        root = pathlib.Path(raw)
        reference = root / "reference.wav"
        output_dir = root / "output"
        worker = root / "worker.py"
        reference.write_bytes(b"0" * 2048)
        worker.write_text("# test worker\n", encoding="utf-8")

        seen_env: dict[str, str] = {}
        previous_setup = cosyvoice_adapter.inspect_setup
        previous_run = cosyvoice_adapter.subprocess.run
        previous_pythonpath = os.environ.get("PYTHONPATH")
        previous_pythonhome = os.environ.get("PYTHONHOME")
        runtime_variables = {
            "BOSSAI_COSYVOICE_ROOT": str(root),
            "BOSSAI_COSYVOICE_MODEL_DIR": str(root),
            "BOSSAI_COSYVOICE_PYTHON": str(worker),
        }
        previous_runtime_variables = {key: os.environ.get(key) for key in runtime_variables}
        os.environ.update(runtime_variables)
        os.environ["PYTHONPATH"] = "C:/foreign-cpython312/site-packages"
        os.environ["PYTHONHOME"] = "C:/foreign-cpython312"

        def fake_run(command, **kwargs):
            seen_env.update(kwargs["env"])
            target = pathlib.Path(command[command.index("--output") + 1])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"1" * 2048)
            return type("Result", (), {"returncode": 0, "stdout": json.dumps({"sampleRate": 24000}), "stderr": ""})()

        try:
            cosyvoice_adapter.inspect_setup = lambda: {"ready": True}
            cosyvoice_adapter.subprocess.run = fake_run
            result = cosyvoice_adapter.render(
                text="local regression check",
                reference_audio=reference,
                output_dir=output_dir,
                worker_path=worker,
            )
            if result["sampleRate"] != 24000 or not pathlib.Path(result["outputPath"]).is_file():
                raise AssertionError(f"unexpected render result: {result}")
            if "PYTHONPATH" in seen_env or "PYTHONHOME" in seen_env:
                raise AssertionError("CosyVoice subprocess inherited a foreign Python package root")
        finally:
            cosyvoice_adapter.inspect_setup = previous_setup
            cosyvoice_adapter.subprocess.run = previous_run
            if previous_pythonpath is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = previous_pythonpath
            if previous_pythonhome is None:
                os.environ.pop("PYTHONHOME", None)
            else:
                os.environ["PYTHONHOME"] = previous_pythonhome
            for key, value in previous_runtime_variables.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    print("RESULT: CosyVoice subprocess environment isolation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
