#!/bin/zsh
# Applies the Lonk patch to a MacNativeGames checkout: ./apply.sh /path/to/MacNativeGames
set -e
repo=${1:?usage: ./apply.sh /path/to/MacNativeGames}
here=${0:A:h}
base=$(<"$here/patches/BASE_COMMIT")
head=$(git -C "$repo" rev-parse HEAD)
[[ $head == $base ]] || echo "note: checkout is at $head, the patch was made against $base"
git -C "$repo" apply --check "$here/patches/lonk.patch"
git -C "$repo" apply "$here/patches/lonk.patch"
echo "Lonk patch applied. Rebuild the TotK app."
