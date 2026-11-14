#!/usr/bin/env bash
# Push this repository to GitHub over SSH on port 443 (no proxy required).
# Usage: bash push_github_443.sh <github-user> <repo-name>
set -euo pipefail

USER=${1:-}
REPO=${2:-}
if [ -z "$USER" ] || [ -z "$REPO" ]; then
  echo "USAGE: bash push_github_443.sh <github-user> <repo-name>"
  echo "Create an EMPTY repository at https://github.com/new first."
  exit 2
fi

cd "$(dirname "$0")"
echo "REPO_DIR=$(pwd)"
echo "LOCAL_COMMIT=$(git log -1 --format='%h %s')"
echo "TRACKED_FILES=$(git ls-files | wc -l)"

echo "--- 1/3 verify SSH over 443 reaches GitHub auth layer ---"
SSH_OUT=$(timeout 20 ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new \
  -o BatchMode=yes -T git@github-443 2>&1 || true)
echo "$SSH_OUT" | head -3
case "$SSH_OUT" in
  *"successfully authenticated"*) echo "SSH_AUTH_OK" ;;
  *"Permission denied (publickey)"*)
    echo "SSH_KEY_NOT_ADDED: add the public key to https://github.com/settings/keys"
    echo "  cat ~/.ssh/id_ed25519_github443.pub"
    exit 3 ;;
  *) echo "SSH_UNEXPECTED: continuing anyway" ;;
esac

echo "--- 2/3 set remote ---"
git remote remove origin 2>/dev/null || true
git remote add origin "git@github-443:${USER}/${REPO}.git"
git remote -v

echo "--- 3/3 push ---"
GIT_SSH_COMMAND="ssh -o ConnectTimeout=15 -o ServerAliveInterval=30 -o StrictHostKeyChecking=accept-new" \
  git push -u origin main
RC=$?
echo "PUSH_RC=$RC"
if [ "$RC" -eq 0 ]; then
  echo "PUSH_OK"
  git ls-remote origin main
else
  echo "PUSH_FAILED rc=$RC ; rerun this script to resume (git resumes the pack)"
fi
exit "$RC"
