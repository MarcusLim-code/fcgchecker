"""Build a source archive, then a wheel from its fresh extraction, entirely offline.

Requires the pinned development/build tools. Never deletes the checkout's build tree.
No dependency resolution, WD services or firmware execution is performed.
"""

import argparse
import hashlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def extract_source(archive: Path, destination: Path) -> Path:
    with tarfile.open(archive) as bundle:
        for item in bundle.getmembers():
            target = (destination / item.name).resolve()
            if not target.is_relative_to(destination.resolve()) or not (
                item.isfile() or item.isdir()
            ):
                raise ValueError("Source archive contains unsafe paths or nonregular files")
            if item.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(item) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    roots = list(destination.iterdir())
    if len(roots) != 1 or not (roots[0] / "pyproject.toml").is_file():
        raise ValueError("Expected exactly one source project")
    return roots[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Fresh artifact directory")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("Output must be a fresh directory")
    output.mkdir(parents=True)
    command = [sys.executable, "-m", "build", "--no-isolation"]
    subprocess.run(
        [*command, "--sdist", "--outdir", str(output), str(ROOT)], check=True, timeout=120
    )
    (archive,) = output.glob("*.tar.gz")
    with tempfile.TemporaryDirectory(prefix="fcgc-build-") as temporary:
        source = extract_source(archive, Path(temporary))
        subprocess.run(
            [*command, "--wheel", "--outdir", str(output), str(source)], check=True, timeout=120
        )
    artifacts = sorted([*output.glob("*.whl"), *output.glob("*.tar.gz")])
    (output / "SHA256SUMS").write_text(
        "".join(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in artifacts
        )
    )


if __name__ == "__main__":
    main()
