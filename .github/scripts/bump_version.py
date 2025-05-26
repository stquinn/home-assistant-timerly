import json
import sys
import semver
import os

MANIFEST_PATH = "custom_components/timerly/manifest.json"

def bump_version(version, bump_type):
    if bump_type == "patch":
        return semver.VersionInfo.parse(version).bump_patch()
    elif bump_type == "minor":
        return semver.VersionInfo.parse(version).bump_minor()
    elif bump_type == "major":
        return semver.VersionInfo.parse(version).bump_major()
    else:
        raise ValueError(f"Unsupported bump type: {bump_type}")

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

    # ✅ Set GitHub Actions output using the environment file
    with open(os.environ["GITHUB_OUTPUT"], "a") as f:
        print(f"new_version={new_version}", file=f)

if __name__ == "__main__":
    main()
