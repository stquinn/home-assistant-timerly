import json
import semver
import os
import subprocess

MANIFEST_PATH = "custom_components/timerly/manifest.json"

def bump_version(current_version: str, bump_type: str) -> str:
    parsed = semver.VersionInfo.parse(current_version)
    if bump_type == "patch":
        return str(parsed.bump_patch())
    elif bump_type == "minor":
        return str(parsed.bump_minor())
    elif bump_type == "major":
        return str(parsed.bump_major())
    else:
        raise ValueError(f"Unsupported bump type: {bump_type}")

def get_bump_type_from_commits() -> str:
    try:
        output = subprocess.check_output([
            "npx", "conventional-recommended-bump", "-p", "angular", "-r", "0"
        ], stderr=subprocess.DEVNULL, text=True)
        for line in output.splitlines():
            if '"releaseType":' in line:
                return line.split('"')[3]
        raise ValueError("Could not parse release type from conventional-recommended-bump")
    except subprocess.CalledProcessError as e:
        raise RuntimeError("Failed to run conventional-recommended-bump") from e

def main():
    with open(MANIFEST_PATH, "r") as f:
        manifest = json.load(f)

    current_version = manifest["version"]
    bump_type = get_bump_type_from_commits()
    new_version = bump_version(current_version, bump_type)
    manifest["version"] = new_version

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        f.write(f"new_version={new_version}\n")
        f.write(f"previous_version=v{current_version}\n")

if __name__ == "__main__":
    main()
