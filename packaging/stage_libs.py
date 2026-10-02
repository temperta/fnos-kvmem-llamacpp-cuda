#!/usr/bin/env python3
"""Stage the shared-library closure of a binary into a target lib directory.

Rules:
  * every resolved dependency OUTSIDE the OS system directories is bundled
    (project libraries like libllama/libggml + CUDA toolkit libraries);
  * libstdc++.so.6 / libgcc_s.so.1 are bundled even though they live in
    system dirs (cross-distro safety);
  * glibc core libraries (libc/libm/libpthread/ld-*) are provided by the OS;
  * libcuda.so.1 / libnvidia-ml.so.1 are supplied by the target's NVIDIA
    driver and are allowed to be missing in the build image.

Iterates ldd with the staging dir on LD_LIBRARY_PATH until the closure
stops growing, then verifies nothing (but the allowed set) is missing.
"""
import os
import shutil
import subprocess
import sys

# 仅这些 glibc 核心库由目标系统提供（fnOS Debian 12 均自带）
EXCLUDE_NAMES = {
    "libc.so.6", "libm.so.6", "libpthread.so.0", "libdl.so.2",
    "librt.so.1", "libresolv.so.2", "libnss_files.so.2",
    "libnss_dns.so.2", "libnss_compat.so.2", "libcrypt.so.1",
}
# 其余依赖（项目库 libllama/libggml、CUDA 工具链库、libnccl、libstdc++/libgcc_s）全部随包分发
ALLOWED_MISSING = {"libcuda.so.1", "libnvidia-ml.so.1"}


def ldd_deps(binary: str, extra_libdir: str | None):
    env = dict(os.environ)
    if extra_libdir:
        env["LD_LIBRARY_PATH"] = extra_libdir + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    out = subprocess.run(["ldd", binary], env=env, capture_output=True, text=True, check=True).stdout
    deps, missing = [], []
    for line in out.splitlines():
        line = line.strip()
        if "=>" not in line:
            continue
        name, rest = line.split("=>", 1)
        rest = rest.strip()
        if rest == "not found":
            missing.append(name.strip())
        else:
            target = rest.split(" (", 1)[0].strip()
            if target:
                deps.append((name.strip(), target))
    return deps, missing


def should_copy(name: str, target: str) -> bool:
    if name in ALLOWED_MISSING or name in EXCLUDE_NAMES:
        return False
    return True


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} BINARY STAGING_LIBDIR", file=sys.stderr)
        return 2
    binary, libdir = sys.argv[1], sys.argv[2]
    if not os.path.isfile(binary):
        print(f"binary not found: {binary}", file=sys.stderr)
        return 2
    os.makedirs(libdir, exist_ok=True)

    copied: set[str] = set()
    for round_no in range(1, 11):
        deps, missing = ldd_deps(binary, libdir)
        missing = [m for m in missing if m not in ALLOWED_MISSING]
        if missing:
            print(f"round {round_no}: MISSING: {missing}", file=sys.stderr)
            return 1
        new = []
        for name, target in deps:
            if should_copy(name, target) and target not in copied \
                    and not os.path.exists(os.path.join(libdir, os.path.basename(target))):
                new.append(target)
        if not new:
            break
        for target in new:
            real = os.path.realpath(target)
            dst = os.path.join(libdir, os.path.basename(target))
            shutil.copy2(real, dst)
            copied.add(target)
            print(f"  staged {os.path.basename(target)} <- {real}")
    else:
        print("closure did not converge", file=sys.stderr)
        return 1

    # final verification
    deps, missing = ldd_deps(binary, libdir)
    missing = [m for m in missing if m not in ALLOWED_MISSING]
    if missing:
        print(f"verification FAILED, missing: {missing}", file=sys.stderr)
        return 1
    for name, target in deps:
        if should_copy(name, target) and not os.path.exists(os.path.join(libdir, os.path.basename(target))):
            print(f"verification FAILED, not staged: {os.path.basename(target)}", file=sys.stderr)
            return 1
    print(f"OK: {len(os.listdir(libdir))} libraries staged into {libdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
