# Nuke a hurricane - generation record

## Voice-over (Higgsfield text2speech_v2, variant elevenlabs, preset voice "Dylan" b847bc29-f184-583a-8ad9-d1f1e16d1a60)

So why don't we just nuke a hurricane? Basically, the storm is way stronger. Noah says it gives off heat like a
ten-megaton bomb every twenty minutes. The blast just passes through, and the storm keeps spinning. And the wind
carries the radioactive fallout back to land.

("Noah" is the phonetic spelling of NOAA so the voice says it as a word.) 47 words, 14.2 s. Job ec07cda1-2ee4-4b9a-a90b-4cc13cd3c8e8.

## Pictures (Higgsfield seedream_5_5, 2k, 3:2, background transparent)

GPT Image 2.5 needs a paid Higgsfield plan, so the free-plan Seedream 5.5 was used. To fit 10 credits, all poses were
generated as ONE pose sheet (no reference = this is the hero) and all props as ONE props sheet referencing it; prep.py
splits and trims them.

### poses.png (job 54579d79-8204-4050-96f5-06c01e82c95a)
A character pose sheet: the SAME cartoon character drawn six times in a 3 x 2 grid ... (1) holding a round black cartoon
bomb with a short fuse and a yellow-and-black radiation symbol, (2) wind-up with the bomb above and behind the head,
(3) follow-through with empty hands, (4) arms crossed smug, (5) confused head scratch, (6) scared facing the viewer,
+ the fixed STYLE_CHAR block from the skill.

### props.png (job 080dd3ee-4850-4d37-b47f-cd04a61a6af9, reference = poses job)
Props sheet in the same style: a cartoon hurricane seen from directly above (round spiral of storm clouds with an eye),
the same bomb alone, a cartoon palm tree; isolated on a transparent background.

## Sound
- boom.wav: Higgsfield mirelo_text_to_audio, "one big cartoon explosion, a punchy deep boom with a short rumbling tail"
  (job 5c2c1693-4415-42ba-9394-dad9a9db6ecd), sliced from its onset at 0.69 s.
- wind, whoosh, gust, pop, tick, shock, boing, boom_small: synthesized in sfx.py (credits ran out).

## Facts (voice-over)
- NOAA AOML hurricane FAQ C5c: heat release of a mature hurricane = a 10-megaton nuclear bomb every 20 minutes; the
  shock wave passes without raising the barometric pressure; fallout would move with the trade winds to land.
  https://www.aoml.noaa.gov/hrd/tcfaq/C5c.html
