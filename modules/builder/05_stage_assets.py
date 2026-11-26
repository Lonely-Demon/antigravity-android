#!/usr/bin/env python3
"""
05_stage_assets.py - Stages runtime, web assets, and manifests into build/staging/assets.
"""
import sys
import os
import shutil
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
MODULES_DIR = os.path.join(PROJECT_ROOT, "modules")
if MODULES_DIR not in sys.path:
    sys.path.insert(0, MODULES_DIR)

from runner import prepare_runtime


def stage_assets(staging_dir, no_bypass=False):
    no_bypass = no_bypass or (os.environ.get("NO_BYPASS") == "1") or (os.environ.get("SKIP_GATES") == "1")
    assets_dir = os.path.join(staging_dir, "assets")
    runtime_dst = os.path.join(assets_dir, "runtime")
    web_dst = os.path.join(assets_dir, "web")
    os.makedirs(assets_dir, exist_ok=True)

    print(f"[*] Staging fully patched runtime assets (no_bypass={no_bypass}) -> {runtime_dst}...")
    ok = prepare_runtime.prepare(dest_runtime_dir=runtime_dst, no_bypass=no_bypass)
    if not ok:
        raise RuntimeError("Failed to prepare and stage runtime assets!")

    web_src = os.path.join(PROJECT_ROOT, "web")
    if os.path.isdir(web_src):
        web_build_script = os.path.join(web_src, "build.sh")
        if os.path.isfile(web_build_script):
            print(f"[*] Building mobile web override bundles via {web_build_script} --overlays-only...")
            subprocess.check_call(["bash", web_build_script, "--overlays-only"], cwd=PROJECT_ROOT)

        core_bin = os.path.join(runtime_dst, "bin", "liblanguage_server.so")
        extract_script = os.path.join(web_src, "extract_upstream.py")
        override_html_script = os.path.join(web_src, "override_html.py")
        patch_main_script = os.path.join(web_src, "patch_main.py")

        if os.path.isfile(core_bin) and os.path.isfile(extract_script):
            print(f"[*] Extracting upstream web UI from {core_bin} -> {web_dst}...")
            subprocess.check_call(["python3", extract_script, core_bin, web_dst], cwd=PROJECT_ROOT)

            gen_src = os.path.join(web_src, "generated")
            gen_dst = os.path.join(web_dst, "generated")
            if os.path.isdir(gen_src):
                shutil.copytree(gen_src, gen_dst, dirs_exist_ok=True)

            print(f"[*] Applying mobile UI overrides onto upstream web bundle...")
            subprocess.check_call(["python3", override_html_script, os.path.join(web_dst, "index.html")], cwd=PROJECT_ROOT)
            subprocess.check_call(["python3", patch_main_script, os.path.join(web_dst, "main.js")], cwd=PROJECT_ROOT)

            if shutil.which("node"):
                subprocess.check_call(["node", "--check", os.path.join(web_dst, "main.js")])
            print("[OK] Staged upstream web UI with mobile overrides.")
        else:
            print(f"[*] Staging static web assets from {web_src} -> {web_dst}...")
            if os.path.exists(web_dst):
                shutil.rmtree(web_dst)
            def web_ignore(directory, files):
                ignored = set()
                rel_dir = os.path.relpath(directory, web_src)
                if rel_dir == ".":
                    for name in ("main.js", "src", "tests", "build.sh", "patch_main.py", "src.manifest", "extract_upstream.py", "override_html.py"):
                        if name in files:
                            ignored.add(name)
                return ignored

            shutil.copytree(web_src, web_dst, ignore=web_ignore)
            print("[OK] Staged web assets.")

    env_src = os.path.join(PROJECT_ROOT, "env", "dist", "env")
    env_dst = os.path.join(assets_dir, "env")
    print(f"[*] Staging env assets from {env_src} -> {env_dst}...")
    manifest_file = os.path.join(env_src, "manifest.json")
    if not os.path.isfile(manifest_file):
        print(f"[*] env manifest missing, building env assets...")
        subprocess.check_call(["bash", os.path.join(PROJECT_ROOT, "env", "build.sh"), "assets"])
    if os.path.exists(env_dst):
        shutil.rmtree(env_dst)
    shutil.copytree(env_src, env_dst)
    print(f"[OK] Staged env assets.")

    print(f"[OK] Staged all assets into {assets_dir}")
    return assets_dir


def main():
    staging_dir = os.path.join(PROJECT_ROOT, "build", "staging")
    no_bypass = (os.environ.get("NO_BYPASS") == "1") or (os.environ.get("SKIP_GATES") == "1")
    for arg in sys.argv[1:]:
        if arg in ("--no-bypass", "--nobypass", "--skip-gates", "--no-gates", "--standard"):
            no_bypass = True
        elif arg in ("--bypass", "--region-bypass", "--with-bypass"):
            no_bypass = False
        elif not arg.startswith("-"):
            staging_dir = arg
    stage_assets(staging_dir, no_bypass=no_bypass)


if __name__ == "__main__":
    main()
