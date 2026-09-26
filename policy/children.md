# Children (applies on top of core.md; cannot be relaxed by any layer)

- **CH-1a** Minor involved (or possibly) in sexual content → B1-1 hard stop.
- **CH-1b** Children as targets of non-sexual text (threats, stigma of children born of rape, deported children) → in scope, High priority, identities never repeated.
  When unsure between the two → CH-1a.
- **CH-2** Age indicators: one is enough together with a sexual element. Types of indicators (the word lists for each language are in the `age_terms` of the region profiles, never here):
  - a stated age under 18, in digits or in words, with or without a unit ("I'm only 12", "fifteen-year-old"), including infants (days, weeks or months old);
  - a word that designates a child (child, kid, baby, teen, pupil, schoolgirl, underage, minor, and their equivalents);
  - a school grade or level;
  - an institution or setting for children (orphanage, children's home, school, camp for transferred children);
  - in images: drawings, cartoon or game characters, or people with a childlike appearance (never an age estimate of a real person's body, see modalities.md).

  Words meaning "girl", "boy" or "young woman" alone are NOT age indicators (commonly used for adults).
- **CH-3** (region-specific: see the region profiles, e.g. the transfer of children in a given conflict.)
- **CH-4** Shaming children born of rape or their mothers = SV-REL-5 + HP-02.
- **CH-5** In code: possible_minor evaluated first; a validator BLANKS content fields even if the model filled them; never in queue, export or training; possible_minor recall reported separately (target 100%), tested on synthetic text only.
