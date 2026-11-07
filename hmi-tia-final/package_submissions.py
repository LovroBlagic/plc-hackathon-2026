"""Wrap the verified native project archives in the required team ZIP names."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parent.parent
    expected = json.loads((repo / "hmi-tia-final/archive_sha256.json").read_text())
    projects = [
        ("TIA_HMI_flicker_fixed_v3.zap21", "strujici_rjesenje_tia.zip"),
        ("ME_v7_WebVisu_dashboard_v2.projectarchive", "strujici_rjesenje_codesys.zip"),
    ]
    # Validate all inputs and destinations before creating either output.
    for source_name, zip_name in projects:
        source = repo / "deliver" / source_name
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != expected[source_name]:
            raise RuntimeError(f"Archive hash mismatch: {source}")
        if (args.out / zip_name).exists():
            raise FileExistsError(args.out / zip_name)
    args.out.mkdir(parents=True, exist_ok=True)
    for source_name, zip_name in projects:
        source = repo / "deliver" / source_name
        destination = args.out / zip_name
        with ZipFile(destination, "x", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            archive.write(source, arcname=source_name)
        with ZipFile(destination) as archive:
            if archive.testzip() is not None or archive.namelist() != [source_name]:
                raise RuntimeError(f"Invalid ZIP: {destination}")
            digest = hashlib.sha256(archive.read(source_name)).hexdigest()
            if digest != expected[source_name]:
                raise RuntimeError(f"Packaged content mismatch: {destination}")
        print(f"VERIFIED {destination}")


if __name__ == "__main__":
    main()
