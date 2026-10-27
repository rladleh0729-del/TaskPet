# 여러 파일을 커밋 하나로 GitHub 에 올린다 (이 PC의 git 은 HTTPS 가 고장이라 gh api 로).
#   python tools\gh_commit.py <owner/repo> <branch> "<메시지>" <로컬 파일>=<저장소 경로> ...
# 올린 파일마다 GitHub 가 계산한 해시가 내 파일의 git 해시와 같은지 확인하고, 다르면 멈춘다.
import base64
import hashlib
import json
import os
import subprocess
import sys

GH = os.environ.get("GH", r"C:\Users\k2000\tools\gh\bin\gh.exe")


def api(path, method="GET", body=None):
    cmd = [GH, "api", path, "-X", method]
    if body is not None:
        cmd += ["--input", "-"]
    r = subprocess.run(cmd, input=json.dumps(body).encode() if body is not None else None,
                       capture_output=True)
    if r.returncode:
        raise SystemExit(f"{method} {path} 실패: {r.stderr.decode('utf-8', 'replace')}")
    return json.loads(r.stdout or b"null")


def git_hash(data):
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def main():
    repo, branch, msg, *pairs = sys.argv[1:]
    base = api(f"repos/{repo}/git/ref/heads/{branch}")["object"]["sha"]
    base_tree = api(f"repos/{repo}/git/commits/{base}")["tree"]["sha"]
    tree = []
    for pair in pairs:
        local, path = pair.split("=", 1)
        data = open(local, "rb").read()
        blob = api(f"repos/{repo}/git/blobs", "POST",
                   {"content": base64.b64encode(data).decode(), "encoding": "base64"})
        if blob["sha"] != git_hash(data):
            raise SystemExit(f"{path}: 올린 내용이 내 파일과 다름")
        tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print("  ", path, blob["sha"][:12])
    new_tree = api(f"repos/{repo}/git/trees", "POST", {"base_tree": base_tree, "tree": tree})
    commit = api(f"repos/{repo}/git/commits", "POST",
                 {"message": msg, "tree": new_tree["sha"], "parents": [base]})
    api(f"repos/{repo}/git/refs/heads/{branch}", "PATCH", {"sha": commit["sha"]})
    print("커밋", commit["sha"][:12], commit["html_url"])


if __name__ == "__main__":
    main()
