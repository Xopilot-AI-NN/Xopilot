"""
Файл: scripts/build_native.py
Разработчик: DenBroLiik
Описание: Сборка и размещение нативной БД для текущего Python на Linux/Windows.
"""

from pathlib import Path
import argparse
import os
import shutil
import subprocess
import sys
import sysconfig

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    command = ["cargo", "build", "--manifest-path", str(ROOT / "Services/Cargo.toml")]
    if not args.debug:
        command.append("--release")
    if args.offline:
        command.append("--offline")
    environment = dict(os.environ, PYO3_PYTHON=sys.executable)
    subprocess.run(command, cwd=ROOT, env=environment, check=True)
    profile = "debug" if args.debug else "release"
    filename = "advanced_xopilot.dll" if sys.platform == "win32" else "libadvanced_xopilot.so"
    source = ROOT / "Services" / "target" / profile / filename
    suffix = sysconfig.get_config_var("EXT_SUFFIX") or (".pyd" if sys.platform == "win32" else ".so")
    destination = ROOT / "App" / ("advanced_xopilot" + suffix)
    staging = destination.with_name(destination.name + ".tmp")
    try:
        shutil.copy2(source, staging)
        os.replace(staging, destination)
    except PermissionError as exc:
        raise RuntimeError("Закройте запущенный Xopilot и повторите сборку нативного модуля.") from exc
    finally:
        staging.unlink(missing_ok=True)
    subprocess.run([sys.executable, "-c", "import advanced_xopilot; print('Native DB import: OK')"],
                   cwd=ROOT / "App", check=True)
    print(destination)


if __name__ == "__main__":
    main()
