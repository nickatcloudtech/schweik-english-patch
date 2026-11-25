The Adventures of the Good Soldier Schweik
English community patch (qdEngine)

This install uses the English localization patch:
  - English subtitles and UI text
  - Original Russian voice acting (voice_mode=original)

The voices are the original performances on purpose. The comedy is in
the delivery, and a generated English dub of 3,946 lines (2,326 of them
Schweik) would say every line in the same tone and mispronounce the
names. An English dub is welcome. Each line in
translation/schweik_dialogue.csv names its .ogg file. Record those
files into patch/voices_en/ and install them with tools/inject_voices.py.
See docs/LOCALIZATION.md, section "Voices".

Configuration: qd_game.ini
  [localization]
  language=english
  voice_mode=original

To install or update the patch, run ./deploy from the qdEngine repository.