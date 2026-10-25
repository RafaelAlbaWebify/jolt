# Bilingual Indeed and LinkedIn search expansion — 2026-10-25

## Principle
Portal language is **not** vacancy language. English and Spanish equivalents must both be discovered for local Vigo/Pontevedra and Spain-eligible remote work. Adding variants increases recall, not guaranteed employability. Preserve the existing 16 Indeed searches until a small bilingual pilot confirms additional qualified leads.

## Missing-language candidates (paired to existing Indeed portfolio)
| Existing | Candidate counterpart | Track |
|---|---|---|
| Application Support | soporte de aplicaciones | IT |
| IT Specialist | técnico informático | IT |
| Technical Support Engineer | ingeniero de soporte técnico | IT |
| Service Desk | mesa de ayuda | IT |
| IT Support | soporte informático | IT |
| IT Operations Analyst | operaciones IT | IT |
| MES Support | soporte MES | industrial |
| Manufacturing IT | informática industrial | industrial |
| Auxiliar administrativo | administrative assistant | transferable |
| Back Office | administrativo back office | transferable |
| Atención al cliente | customer support | transferable |
| Teleoperador | call center agent | transferable |
| Administrativo logística | logistics administrator | transferable |
| Data Entry | entrada de datos | transferable |
| Customer Service | servicio al cliente | transferable |
| Recepcionista | receptionist | transferable |

This is a *candidate expansion*, not 16 more production searches to activate blindly. For uncommon translations, compare actual titles and unique eligible opportunities. Use separate keyword searches before trying Boolean OR due to demonstrated broad-query noise.

## LinkedIn-specific rules
- URL search: `https://www.linkedin.com/jobs/search/?keywords=...&geoId=...&sortBy=DD`; documented JOLT historical geoIds need validation in live captures.
- `f_WT=2` filters remote on LinkedIn, **not** eligibility to work in Spain; read the job description.
- `f_TPR=r604800` is a rolling week. Do not assume all postings are included when site ranking/algorithm changes.
- Separate local ES/EN and Spain-remote ES/EN. Preserve international contractor/B2B lane when explicit Spain eligibility exists.
- Dedupe within portal by verified ID; across portal and languages by company, title synonyms, location, job description and requisition reference. Existing `/api/discovery-duplicate-candidates` and human confirmation are available. Never silently merge or delete postings.

## Promotion gates
1. Small bounded capture (10 per counterpart, preferably prioritized pairs) with no modification to production saved searches.
2. Compare unique *eligible* leads against existing English/Spanish counterpart and against all portals.
3. Preserve bilingual variant only when it adds useful coverage; reject spam, unrelated jobs and duplicates.
4. Back up existing saved searches before replacing any portfolio. Change Indeed via `/api/discovery-searches`, LinkedIn via `/api/linkedin-searches`; don't conflate their storage.
