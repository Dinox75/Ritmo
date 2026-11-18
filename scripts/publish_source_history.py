"""Sync the explicit source-only release catalog. Run without --publish to validate."""
import argparse
import json
import re
import subprocess
from pathlib import Path

REPO = "Dinox75/Ritmo"
ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / "docs" / "releases"
TAG = re.compile(r"v0\.1\.0-(?:alpha\.[1-9][0-9]*\.source|preview\.[1-9][0-9]*-source)")
SHA = re.compile(r"[0-9a-f]{40}")


def call(*command):
    return subprocess.check_output(command, cwd=ROOT, text=True, encoding="utf-8")


def catalog():
    history = set(call("git", "rev-list", "--first-parent", "HEAD").splitlines())
    entries = json.loads((NOTES / "catalog.json").read_text(encoding="utf-8"))
    used_tags = set()
    for item in entries:
        tag, commit, title = (item[key] for key in ("tag", "commit", "title"))
        if not TAG.fullmatch(tag) or tag in used_tags:
            raise SystemExit(f"Tag de código-fonte inválida ou duplicada: {tag}")
        if not SHA.fullmatch(commit) or commit not in history:
            raise SystemExit(f"{tag}: commit fora da linha principal")
        if not title.strip() or not (NOTES / f"{tag}.md").read_text(encoding="utf-8").strip():
            raise SystemExit(f"{tag}: título ou notas vazios")
        used_tags.add(tag)
    return entries


def tags_on_github():
    raw = call("git", "ls-remote", "--tags", f"https://github.com/{REPO}.git")
    tags, peeled = {}, {}
    for line in raw.splitlines():
        sha, ref = line.split("\t", 1)
        name = ref.removeprefix("refs/tags/")
        if name.endswith("^{}"):
            peeled[name[:-3]] = sha
        else:
            tags[name] = sha
    return tags | peeled


def releases_on_github():
    pages = json.loads(call("gh", "api", "--paginate", "--slurp", f"repos/{REPO}/releases"))
    return {rel["tag_name"]: rel for page in pages for rel in page}


def publish(entries):
    tags, releases = tags_on_github(), releases_on_github()
    # Validate every entry before the first write.
    for item in entries:
        tag, commit = item["tag"], item["commit"]
        if tag in tags and tags[tag] != commit:
            raise SystemExit(f"{tag}: tag existente aponta para outro commit")
        if tag in releases:
            entry = releases[tag]
            if tags.get(tag) != commit or not entry["prerelease"] or entry["draft"] or entry["assets"]:
                raise SystemExit(f"{tag}: a release existente não corresponde ao canal de código-fonte")
    for item in entries:
        tag, commit, title = (item[key] for key in ("tag", "commit", "title"))
        file = NOTES / f"{tag}.md"
        if tag not in tags:
            call("gh", "api", "-X", "POST", f"repos/{REPO}/git/refs",
                 "-f", f"ref=refs/tags/{tag}", "-f", f"sha={commit}")
        if tag not in releases:
            call("gh", "release", "create", tag, "--repo", REPO, "--verify-tag",
                 "--prerelease", "--latest=false", "--title", title, "--notes-file", str(file))
        else:
            current = releases[tag]
            if current["name"] != title or current["body"].strip() != file.read_text(encoding="utf-8").strip():
                call("gh", "release", "edit", tag, "--repo", REPO,
                     "--title", title, "--notes-file", str(file))
    for item in entries:
        tag = item["tag"]
        result = json.loads(call("gh", "release", "view", tag, "--repo", REPO,
                                 "--json", "url,isDraft,isPrerelease,assets"))
        if result["isDraft"] or not result["isPrerelease"] or result["assets"]:
            raise SystemExit(f"{tag}: verificação da publicação falhou")
        print(result["url"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    entries = catalog()
    if args.publish:
        publish(entries)
    else:
        for item in entries:
            print(item["tag"], item["commit"], item["title"])


if __name__ == "__main__":
    main()
