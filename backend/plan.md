have (presume):
- address in consistent format
- data in json w the following db:
    - 311 complaints
    - hpd violations
    - dob permits
    - rodent inspections

evaluation phase 1: normal 
- normalize data per unit
- safety & severity issues weight 35
    - class i: immediate hazard, -20
    - class a: resolve in 90 (non-severe), -5
    - class b: hazardous, -10
    - class c: immediate hazard, -20 (idk why db uses class c and class i?)
- building conditions weight 25
    - similar
- pest conditions weight 15
    - count
- responsivenes weight 15
    - open reports / within due
    - resolved promptly
    - resolved late (date calc)
    - open unresolved (date calc)
    - dismissed
- recency / trends weight 10
    - 0-6 mo
    - 6-12 mo
    - 12-24 mo
    - 24+ mo

evaluation phase 2: gemini explanations
- "make no mistakes"
- make sure we say this evaluation is based on data with an ai overview lmao
    - "You explain a building score calculated by a deterministic scoring system.
        Rules:
        - Do not recalculate or modify any score.
        - Use only facts present in the supplied data.
        - Do not treat complaints as confirmed conditions.
        - Mention important missing or stale data.
        - Make comparisons only when comparison statistics are supplied.
        - Return valid JSON matching the required schema.
        - Keep the summary understandable to a renter.
        - Avoid legal, medical, or safety guarantees.

        Scoring result:
        {{score_result}}

        Supporting evidence:
        {{building_data}}"
- fixed enum 
    - overall: good, poor, mixed
    - prospects: improving, worsening, stable, n/a (not enough data)
    - confidence: high, low, medium
* relative to other nearby housing options
* relative to similar cost housing

plan:
- test gemini api thru simple file
- create sample json and calculate (phase 1)
- connect calculations to gemini (phase 2)