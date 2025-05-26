import json
import sys
import semver
import os

MANIFEST_PATH = "custom_components/timerly/manifest.json"

def bump_version(version, bump_type):
    v = semver.VersionInfo.parse(version)
    if bump_type == "patch":
        return v.bump_patch()
    elif bump_type == "minor":
        return v.bump_minor()
    elif bump_type == "major":
        return v.bump_major()
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")

def main():
    bump_type = sys.argv[1]

    with open(MANIFEST_PATH, "r") as f:
        manifest = json.load(f)

    current_version = manifest["version"]
    new_version = str(bump_version(current_version, bump_type))
    manifest["version"] = new_version

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        print(f"new_version={new_version}", file=f)
        print(f"previous_version=v{current_version}", file=f)

if __name__ == "__main__":
    main()
