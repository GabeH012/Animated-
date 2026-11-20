#!/usr/bin/env bash
# gen.sh NAME ASPECT "PROMPT" [ref1.png] [ref2.png]
#   Generates one transparent cut-out with Higgsfield GPT Image 2.5 into raw/NAME.png (run from images/<short>/).
#   KIND=obj for props / set pieces (uses STYLE_OBJ), default is a character pose (STYLE_CHAR).
#   BACKGROUND=opaque to get a flat light-blue background for keying with key.py instead.
# Kept as a separate file so positional parameters are never touched by skill-text argument substitution.
set -euo pipefail

NAME="$1"; ASPECT="$2"; PROMPT="$3"; shift 3
refs=(); for r in "$@"; do refs+=(--image "$r"); done

STYLE_CHAR="Flat 2D cartoon in exactly the same drawing style as the reference images: the same simple white \
character with a big round head, a small soft body, noodle arms with simple four-finger hands and short legs with \
rounded feet, thick smooth black outlines of even weight, flat white fill with a very soft pale-grey shade on one side, \
small solid black oval eyes, simple curved black eyebrows, no nose, no hair, no clothes, a pink tongue only when the \
mouth is open. Clean vector-like linework, flat colours, no texture, no text, no border. Isolated on a fully \
transparent background: no sky, no ground, no floor shadow."
STYLE_OBJ="Flat 2D cartoon in exactly the same drawing style as the reference images: thick smooth black outlines of \
even weight, flat colours with one simple soft shade, clean vector-like linework, no texture, no text, no border, no \
characters. Isolated on a fully transparent background: no sky, no ground, no floor shadow."

if [[ "${KIND:-char}" == "obj" ]]; then STYLE="$STYLE_OBJ"; else STYLE="$STYLE_CHAR"; fi
BG="${BACKGROUND:-transparent}"
if [[ "$BG" == "opaque" ]]; then
  STYLE="${STYLE/Isolated on a fully transparent background/On a plain flat solid light-blue background (#9BCFFD), nothing else}"
fi

mkdir -p raw
higgsfield generate create gpt_image_2_5 --prompt "$PROMPT $STYLE" "${refs[@]}" --aspect_ratio "$ASPECT" \
  --resolution 4k --quality high --background "$BG" --wait --wait-timeout 20m --json > "raw/$NAME.json"
url=$(node -e "console.log(JSON.parse(require('fs').readFileSync(process.argv[1],'utf8'))[0].result_url)" "raw/$NAME.json")
curl -fsS -o "raw/$NAME.png" "$url"
echo "raw/$NAME.png"
