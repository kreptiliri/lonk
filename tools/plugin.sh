#!/bin/zsh
# Builds Lonk's hot-reload plugin: world_survey.c as a dylib. A game started with TOTK_LONK_PLUGIN=<that file> picks up
# each new build within half a second, without a restart (and keeps Lonk where he is).
# usage: plugin.sh <MacNativeGames checkout> <build tree, e.g. TOTK_build/totk> [out.dylib]
set -e
src=${1:?MacNativeGames checkout}/games/totk; tree=${2:?build tree}; out=${3:-$HOME/Library/Application Support/MacNativeGames/lonk.dylib}
mkdir -p "${out:h}"
tmp="$out.partial.dylib"
xcrun clang -std=c11 -O2 -g -Wall -Wextra -Werror -Wno-deprecated-declarations -dynamiclib -undefined dynamic_lookup \
  -DTOTK_GAME_V143=1 -DLONK_PLUGIN=1 -I"$src/third_party/d2r_gfx/gfx/nvn/include" -I"$tree/build/v143" -I"$tree/build" -I"$src/runtime" \
  "$src/runtime/world_survey.c" -o "$tmp"
codesign --force --sign - "$tmp" 2>/dev/null
mv -f "$tmp" "$out"   # one rename: the game never sees half a file
echo "plugin: $out"
