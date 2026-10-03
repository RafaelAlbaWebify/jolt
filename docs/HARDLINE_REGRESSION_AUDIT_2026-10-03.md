# Historical Hard-Filter Regression Audit — 2026-10-03

## Purpose

This audit converts JOLT's manually corrected false positives into a permanent regression set.

Core invariant:

> Technical fit must never override a hard blocker in language, employment geography/location, residence or work authorization, security clearance, mandatory certification, or explicit minimum experience. Ambiguous evidence must remain HOLD/VERIFY and must never become automatic `pursue` or `strong_pursue`.

Production rules are evidence-driven. Company names appear only in regression fixtures and audit documentation; they are not production predicates.

## Historical regression set

| Case | Historical classification | Missed hardline / failure mode | v12 expected behavior | Permanent coverage |
| --- | --- | --- | --- | --- |
| PSI CRO France | Positive/preparing path reconstructed from prior workflow; exact score not preserved in the current audit artifact | France-based employment was allowed to survive technical fit | REJECT when France employment scope is explicit | Corpus case |
| Nortal | `pursue`, technical fit 88 | Mandatory German was not treated as dominant | REJECT | Corpus + language hardline test |
| Prosana | `pursue`, technical fit 84 | Mandatory Lithuanian was not treated as dominant | REJECT | Corpus + language hardline test |
| BV TECH | `pursue`, technical fit 88 | Italy/local employment and unsupported-language context did not dominate fit | REJECT | Corpus + language hardline test |
| ACTION ICT | `pursue`, technical fit 88 | Bologna/partial smart-working employment scope was treated as merely informational | REJECT | Corpus + language/geography regression |
| Mediatica Digital | `conditional`; technical fit was not materialized in the preserved review | Italy/Italian-language eligibility remained unresolved but positive | HOLD/VERIFY or REJECT when explicit blocker evidence is present; never auto-pursue | Corpus + language hardline test |
| LucidLink | `strong_pursue`, technical fit 91 | “Anywhere in the US” was not allowed to dominate a high technical score | REJECT | Corpus |
| Unily | `strong_pursue`, technical fit 92 | US requisition / local employment evidence remained conditional despite source scope | REJECT when US employment scope is explicit | Corpus |
| Prompt Health | `pursue`, technical fit 92 | US employment scope remained conditional | REJECT | Corpus |
| Nebius | `strong_pursue`, technical fit 91 | US scope plus mandatory specialist/primary IAM experience was not dominant | REJECT | Corpus |
| Stripe / Metronome | `strong_pursue`, technical fit 94 | US requisition survived because geography remained conditional | REJECT | Corpus |
| GT Global Services | `pursue`, technical fit 88 | `Remote (USA)` plus required networking certification (e.g. CCNA) did not dominate fit | REJECT | Corpus + mandatory-certification tests |
| Lumen | `pursue`, technical fit 80 | Poland work-from-home position was treated as location metadata rather than employment geography | REJECT | Corpus |
| Taraki / ARC9 | `pursue`, technical fit 80 | Locality / EST-night-shift employment context did not close eligibility | REJECT | Corpus |
| Exa Capital / PrecisionCare | `pursue`, technical fit 88 | `Remote (USA)` plus explicit 1+ year EHR/healthcare-SaaS requirement was not dominant | REJECT for US scope; HOLD/VERIFY for the explicit tenure requirement if geography is otherwise valid | Corpus + 1-year domain-experience regression |
| KPA | `pursue`, technical fit 80 | US employment scope survived high fit | REJECT | Corpus |
| Russell Tobin | `pursue`, technical fit 80 | US/W2 work-right scope did not dominate fit | REJECT | Corpus |
| Fever | `conditional`, technical fit 72 | Hiring location / territorial eligibility was unresolved instead of closed | REJECT when territorial employment is explicit; otherwise HOLD/VERIFY | Corpus |
| Aircall | `pursue`, technical fit 80 | Portugal-only employment scope did not dominate fit | REJECT | Corpus |
| Moxie | `pursue`, technical fit 80 | Philippines-only employment scope did not dominate fit | REJECT | Corpus |
| Tailscale | `pursue`, technical fit 86 | US employment/work-right scope remained conditional | REJECT | Corpus |
| Outmarket AI | `pursue`, technical fit 84 | US/India requisition scope was not closed before fit | REJECT | Corpus |
| PTG / Courser | Historical `pursue` 88 in earlier review; later conditional variants also exist | US-only work scope was treated as non-authoritative location metadata | REJECT | Corpus |
| Roy Jorgensen | Historical positive/conditional path; manual source review estimated ~90% career fit | Frederick, Maryland employment package and US-only employment signals were not dominant | REJECT | Corpus |
| Anaconda | `pursue`, technical fit 88 | Austin, TX / US employment evidence survived technical fit | REJECT | Corpus |
| Beckman Coulter Italy | Historical correction ended in reject; earlier hardline parsing had incorrect/insufficient reason attribution | Italy role + mandatory Italian must be the dominant reason | REJECT | Corpus + language hardline test |
| Tilla | `conditional`, technical fit 92 | Spain-compatible employment was not established; evidence was insufficient, not safely positive | HOLD/VERIFY; never auto-pursue | Corpus |
| Jobright | Multiple historical `conditional` reviews, typically technical fit 75–84 | Remote country scope was unverified and aggregator evidence was not authoritative enough | HOLD/VERIFY or REJECT when explicit foreign employment is established; never auto-pursue | Corpus |
| TheyDo | `strong_pursue`, technical fit 91 | Global-remote company language obscured role-specific North America / US East Coast customer territory | HOLD/VERIFY unless role-specific eligibility is proven; never auto-pursue | Corpus |
| Newmark | Historical high-fit cloud/support candidate; exact preserved score not recovered in this audit pass | Poland hiring location was not allowed to dominate role fit | REJECT | Corpus |
| ENCAMINA | `pursue`, technical fit 88 | LinkedIn/aggregated work-model evidence did not reflect authoritative employer-source hybrid/location constraints | HOLD/VERIFY on source conflict; never auto-pursue | Corpus |

## Gaps found by the regression work

The historical 31-company corpus itself no longer produced an automatic pursue under the current strategy path. The audit nevertheless exposed three generic policy gaps that were not consistently protected by durable tests:

1. **Mandatory certification** — a requirement such as `CCNA certification required` now rejects when the credential is not evidenced by the candidate profile. A preferred certification does not block. An unspecified mandatory certification becomes HOLD/VERIFY.
2. **Explicit minimum experience from one year upward** — requirements such as `1+ years of EHR support experience` or `at least 1 year of ... experience is required` now produce HOLD/VERIFY when candidate tenure cannot be proven. Company-history statements are explicitly excluded.
3. **Clearance eligibility ambiguity** — `active security clearance required` remains a hard reject when not evidenced, while `must be eligible/able to obtain a clearance` becomes HOLD/VERIFY.

## Engine version

These changes are strategy-semantic changes, so the authoritative strategy engine is bumped from `profile-rules-v11` to `profile-rules-v12`. Persisted v11 evaluations must not be treated as current under v12 semantics.

## Regression contract

Every case in the historical corpus must satisfy one of two outcomes:

- **Clear blocker:** `do_not_pursue`.
- **Incomplete/conflicting evidence:** `pursue_if_condition_met` or manual review.

No case in the corpus may return `pursue` or `strong_pursue`.

Additional negative controls ensure that:
- preferred certifications do not block;
- candidate-evidenced mandatory certifications do not block;
- company age/history is not misread as candidate minimum experience;
- ambiguous clearance eligibility does not become an automatic reject or automatic pursue.
