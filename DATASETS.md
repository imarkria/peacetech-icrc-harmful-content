# Candidate datasets

Datasets that could help detect harmful content related to sexual violence (SV). They're grouped by how directly they fit the challenge.

> **Reminder:** don't commit any of this data. Download it into `data/` (already in `.gitignore`) and check each dataset's license and terms of use before you use it. Some are licensed for research only or require you to ask for access.

Access key: 🟢 open download · 🟡 registration, request or form · 🔴 tweet IDs only (you'd have to rehydrate them, which is now hard with the X API)

## 1. Directly about sexual violence and harassment (text)

| Dataset | Content | Size / labels | Lang | Access |
|---|---|---|---|---|
| **SafeCity** (Karlekar & Bansal, EMNLP 2018) | Personal stories of sexual harassment from the SafeCity forum | 9,892 stories. Multi-label: groping, ogling, commenting (plus 10 sparser forms) | EN (India) | 🟢 [github.com/swkarlekar/safecity](https://github.com/swkarlekar/safecity) (research only; SafeCity asks you to contact them) |
| **GBV Tweet Classification** (Zindi / AFD) | Tweets about gender-based violence | ~39.6k tweets in 5 classes: sexual violence (82%), physical, emotional, economic, harmful traditional practices | EN (Africa-focused) | 🟢 [Zindi](https://zindi.africa/competitions/gender-based-violence-tweet-classification-challenge/data) · [Kaggle mirror](https://www.kaggle.com/datasets/gauravduttakiit/gender-based-violence-tweet-classification) |
| **#MeTooMA** (ICWSM 2020) | #MeToo tweets | 9,973 tweets labelled for relevance, stance, hate, sarcasm and dialogue acts (allegation, refutation, justification) | EN | 🔴 [HF `midas/metooma`](https://huggingface.co/datasets/midas/metooma) · [GitHub](https://github.com/midas-research/MeTooMA) |
| **Victim-blaming tweets** (Suvarna et al., 2020) | Tweets discussing sexual assault | 5,070 tweets, 1,562 victim-blaming | EN | 🟡 [ACL Anthology](https://aclanthology.org/2020.acl-srw.43/), ask the authors |
| **ConvAbuse** (Cercas Curry et al., 2021) | Abuse directed at conversational agents | Includes sexism and sexual-harassment labels | EN | 🟢 [github.com/amandacurry/convabuse](https://github.com/amandacurry/convabuse) |
| **Uli dataset** (Tattle, 2024) | Online gender-based violence on Twitter | OGBV labels, annotated by activists | HI, TA, Indian EN | 🟢 [github.com/tattle-made/uli_dataset](https://github.com/tattle-made/uli_dataset) |

## 2. Sexism and misogyny (closely related harmful speech)

| Dataset | Content | Size / labels | Lang | Access |
|---|---|---|---|---|
| **EDOS** (SemEval-2023 Task 10) | Gab and Reddit comments | 20k labelled. Hierarchy: sexist or not → 4 categories (incl. **threats**) → 11 fine-grained vectors. Plus 2M unlabelled | EN | 🟢 [github.com/rewire-online/edos](https://github.com/rewire-online/edos) |
| **EXIST 2023–2025** (CLEF) | Tweets, memes, TikTok videos | Sexism identification, intention and category. Includes a "sexual violence" category, with annotator disagreement kept | EN, ES | 🟡 [nlp.uned.es/exist2025](https://nlp.uned.es/exist2025/) (sign an agreement) |
| **Call Me Sexist But** (Samory et al., 2021) | Tweets, survey items, adversarial rewrites | Sexist content or phrasing | EN | 🟢 [GESIS](https://search.gesis.org/research_data/SDN-10.7802-2251) |
| **MAMI** (SemEval-2022 Task 5) | Misogynous memes (image + text) | 11k memes. Sub-labels: shaming, stereotype, objectification, **violence** | EN | 🟡 [GitHub](https://github.com/MIND-Lab/SemEval2022-Task-5-Multimedia-Automatic-Misogyny-Identification-MAMI-) (on request, academic use) |
| **ArMI / Let-Mi** | Arabic misogyny on Twitter | ~9.8k tweets. 7 misogynistic behaviours (incl. sexual harassment, threat of violence) | AR (+ Levantine) | 🟡 [ArMI](https://sites.google.com/view/armi2021/) · [Let-Mi paper](https://arxiv.org/abs/2103.10195) |
| **SWSR** | Weibo sexism | Sexism labels | ZH | 🟢 [Zenodo](https://zenodo.org/record/4773875) |
| **GBV-Resources** (index) | A catalogue of about 30 more GBV, sexism and misogyny datasets | — | many | 🟢 [github.com/HWU-NLP/GBV-Resources](https://github.com/HWU-NLP/GBV-Resources) |

## 3. General toxicity and safety datasets with a sexual-content label

Useful for pre-training, negative examples, or a baseline classifier. Keep in mind that "sexual" in these sets usually means *explicit* content, which isn't the same thing as *sexual violence*.

| Dataset | SV-relevant labels | Size | Access |
|---|---|---|---|
| **Jigsaw Unintended Bias / Civil Comments** | `sexual_explicit`, `threat`, identity (gender) | ~2M comments | 🟢 [HF `google/civil_comments`](https://huggingface.co/datasets/google/civil_comments) (CC0) |
| **Nemotron / Aegis Content Safety 2.0** (NVIDIA) | Sexual, Sexual (minor), Harassment, Violence, Threat | 33k interactions | 🟢 [HF](https://huggingface.co/datasets/nvidia/Aegis-AI-Content-Safety-Dataset-2.0) (CC-BY-4.0) |
| **OpenAI moderation eval** | sexual, sexual/minors, harassment, violence | 1,680 | 🟢 [github.com/openai/moderation-api-release](https://github.com/openai/moderation-api-release) |
| **BeaverTails** | Sexually explicit, child abuse, violence | 330k QA pairs | 🟢 [HF](https://huggingface.co/datasets/PKU-Alignment/BeaverTails) |
| **WildGuardMix** (AI2) | Sexual content, violence, toxic language | 87k | 🟡 [HF](https://huggingface.co/datasets/allenai/wildguardmix) (gated) |
| **Measuring Hate Speech** (Berkeley) | Continuous hate score, `target_gender_women`, violence item | 136k annotations | 🟢 [HF](https://huggingface.co/datasets/ucberkeley-dlab/measuring-hate-speech) |

## 4. Conflict context (the ICRC angle)

These give you conflict-related SV (CRSV) ground truth, event data and domain vocabulary, and help with low-resource languages spoken in conflict zones.

| Dataset | What it gives you | Access |
|---|---|---|
| **SVAC**: Sexual Violence in Armed Conflict (PRIO / Harvard) | Coded reports of CRSV by armed actor and year, 1989–2023: prevalence, perpetrators, victims, forms. Good for country/actor priors and for building a lexicon | 🟢 [sexualviolencedata.org/dataset](http://www.sexualviolencedata.org/dataset/) |
| **ACLED**: "Sexual violence" sub-event | Geolocated events with free-text `notes` describing each incident, which you can use as positive examples for classifying SV in news-style text | 🟡 [acleddata.com](https://acleddata.com/) (free account, API key) · [coding notes](https://acleddata.com/knowledge-base/how-is-sexual-violence-coded-in-acled-data/) |
| **UN SG annual CRSV reports** (S/2014/181 … S/2024/292) | Authoritative text on CRSV patterns. Good for domain-adaptive pretraining, retrieval (RAG) or a keyword seed list | 🟢 [ReliefWeb](https://reliefweb.int/report/world/conflict-related-sexual-violence-report-secretary-general-s2024292-enarruzh) (bulk: ReliefWeb API) |
| **Telegram HRV dataset** (Nemkova et al., 2023) | 2.3M Russia/Ukraine war Telegram posts, plus a sentence-level human-rights-violation annotation | 🟡 [arXiv 2306.05370](https://arxiv.org/abs/2306.05370) (ask the authors) |
| **AfriHate** (NAACL 2025) | Hate and abuse tweets in 15 African languages, incl. Amharic, Tigrinya, Oromo, Somali, Swahili, Hausa, Kinyarwanda. Includes lexicons | 🟢 [HF `afrihate/afrihate`](https://huggingface.co/datasets/afrihate/afrihate) |
| **Russia–Ukraine multimodal hate speech** (CASE 2022) | Hate speech in war-related social posts | 🟡 [ACL Anthology](https://aclanthology.org/2022.case-1.1.pdf) |

## Suggested starting set

1. **Core classifier:** EDOS (Category 2 "threats" + fine-grained labels), plus the SV class from the GBV Tweet Classification set and SafeCity. Together these give you an "SV / harassment / sexism / benign" label space.
2. **Negatives and robustness:** Civil Comments and Aegis 2.0, so the model learns the difference between explicit-but-consensual content and violent content.
3. **Conflict domain:** ACLED SV `notes` and UN CRSV reports as in-domain positives, to adapt a model to news and report language.
4. **Multilingual:** AfriHate, ArMI and EXIST (ES) for the languages ICRC operations work in.

## Gaps to raise with the ICRC

- No public dataset specifically labels **social-media content about conflict-related sexual violence**. Examples of what's missing: threats of rape used as a weapon, glorification of it, denial of it, and survivors being identified or doxxed. Creating a small annotated set could itself be a hackathon deliverable.
- Most sets are tweet-based and in English. Content from Telegram, TikTok, Facebook and in local languages is underrepresented.
- **Never** collect or handle imagery of sexual abuse, and especially not child sexual abuse material. Stick to text, and report anything you find through the proper channels.
