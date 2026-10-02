#!/usr/bin/env python3
"""Stage the shared-library closure of a binary into a target lib directory.

Rules:
  * libraries from the CUDA toolkit (/usr/local/cuda) are bundled;
  * libstdc++.so.6 / libgcc_s.so.1 are bundled for cross-distro safety;
  * glibc core libraries (libc/libm/libpthread/ld-*) are provided by the OS.

Iterates ldd with the staging dir on LD_LIBRARY_PATH until the closure
stops growing, then verifies nothing is missing.
"""
import os
import shutil
import subprocess
import sys

COPY_PREFIXES = ("/usr/local/cuda",)
COPY_NAMES = {"libstdc++.so.6", "libgcc_s.so.1"}


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
        if missing:
            print(f"round {round_no}: MISSING: {missing}", file=sys.stderr)
            return 1
        new = []
        for _name, target in deps:
            base = os.path.basename(target)
            should_copy = any(target.startswith(p) for p in COPY_PREFIXES) or base in COPY_NAMES
            if should_copy and target not in copied and not os.path.exists(os.path.join(libdir, base)):
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
    if missing:
        print(f"verification FAILED, missing: {missing}", file=sys.stderr)
        return 1
    for _name, target in deps:
        base = os.path.basename(target)
        if any(target.startswith(p) for p in COPY_PREFIXES) or base in COPY_NAMES:
            if not os.path.exists(os.path.join(libdir, base)):
                print(f"verification FAILED, not staged: {base}", file=sys.stderr)
                return 1
    print(f"OK: {len(os.listdir(libdir))} libraries staged into {libdir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
