# Modalities (core layer: every platform, every region)

Same definitions (core.md, children.md) for every format. Only the READING changes: what counts as the item, which layers exist, and what the model may look at. No modality adds or removes a definition, an exclusion or a barrier. In particular Axis 1 is unchanged: hate speech without a relation to sexual violence (HI-TYPE-04 alone) keeps `primary_relation` null and is not flagged, whatever the format.

`modality` = text | image | meme | video | audio (one per item, set from the input, not guessed).

## MOD-TEXT
The item is the text itself (post, caption, comment, transcript given as text). Layers from the platform profile.

## MOD-IMG Image (no text, or text that is only incidental)
- The visual is used ONLY for (a) the conflict link (SV-EL-C: CONF-1 uniform, insignia, weapon; CONF-4 checkpoint, detention, ruins, camp) and (b) signs of manipulation (possible_manipulated_media: collage, edited or recycled picture, AI artefacts, caption contradicting the picture).
- NEVER used to identify a person (no face recognition, no naming, no guessing identity, B1-3); NEVER describe a body or an act (B1-2), even when asked; never estimate the age of a real person from their body. Possible minor with any sexual element → B1-1, and the image is not described at all.
- Visible identity markers (name tag, school, address, unit patch) only raise `identifiable_person`; they are never repeated.
- Layers: `image` (the visual), `embedded_text` (text written in the image, OCR or given).

## MOD-MEME Meme (image + embedded text)
- The meaning is the COMBINATION of the image and the embedded text, not either alone. A harmless picture with a hateful caption, or a harmless caption over a picture that turns it into an attack, are both harmful.
- Irony, sarcasm or mismatch between picture and text can INVERT the literal meaning: judge what the meme communicates to its intended audience (FT-STANCE mocks / endorses), not the literal words. A meme mocking a hateful idea is not hate; a "joke" that demeans a group is.
- Stereotypes rendered as humour still count as harmful information (HI-TYPE-04 when they demean a group based on identity, HP-04 when they dehumanise); this is Axis 2 only.
- Layers: `image`, `embedded_text`, `meme` (the harm only exists in the combination).

## MOD-VID Video
- Each layer is judged separately, then combined: `speech` (transcript), `on_screen_text` (OCR of frames), `caption` (title, description, post text), `sound` (music, chants, non-speech audio), `visuals` (sampled frames: conflict link and manipulation only, same limits as MOD-IMG).
- `triggered_layer` = the layer that carries the harm; when only the combination does, the layer that makes it harmful (e.g. harmless visuals + threatening speech = `speech`).
- A condemning caption over harmful footage: the caption is a separate speaker (like a forwarded or quoted original in the platform profile): assess both, the footage still counts for leads.

## MOD-AUD Audio (voice message, audio track)
- Judged on the transcript (`speech`) and non-speech sound (`sound`). Voice is never used to identify a person (B1-3).

## Reviewer protection (all non-text modalities)
- The model never outputs a description of the visual beyond what the decision needs (conflict link, manipulation); reviewer_summary stays text-only and non-graphic.
- Explicit imagery is quarantined BEFORE the model (hash + reason), never sent to the model, never shown, never used for training; it is counted, not hidden.
