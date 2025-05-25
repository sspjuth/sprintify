#!/bin/bash
set -euo pipefail

# Function to print errors
error() {
  echo "Error: $1" >&2
  exit 1
}

rm -rf dist/*

# Ensure required tools are installed
command -v git >/dev/null 2>&1 || error "git is not installed."
command -v python3 >/dev/null 2>&1 || error "python3 is not installed."
command -v twine >/dev/null 2>&1 || error "twine is not installed."

# Ensure git status is clean
if [[ -n $(git status --porcelain) ]]; then
  error "Working directory not clean. Commit or stash changes first."
fi

# Get last tag and bump
last_tag=$(git tag --sort=-v:refname | head -n1)
if [[ ! $last_tag =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  error "Last tag '$last_tag' is not in the format X.Y.Z"
fi

IFS='.' read -r major minor patch <<< "$last_tag"
new_tag="$major.$minor.$((patch + 1))"

echo "Last tag: $last_tag"
echo "New tag: $new_tag"

# Tag and push
git tag "$new_tag" || error "Failed to create git tag."
git push origin main --tags || error "Failed to push tags."

# Build and upload with version env variable
export RELEASE_VERSION="$new_tag"
python3 -m build  || error "Build failed."
twine upload dist/* || error "Twine upload failed."

echo "Release $new_tag complete."