# Audit scripts used in the review

`audit_tables.py REPO_ROOT` recomputes, from the released run-level CSVs (standard library only):

- the S4->S5 paired change per policy (exact sign-flip, Holm over 8);
- the S4->S5 difference-in-differences against Hungarian (Holm over 7);
- S4 and S5 energy per completed request;
- the determinism check (ablation alpha_E = 1 means vs nominal runs on the same 18 seeds);
- the ablation SDs and exact p-values;
- the list of S4 nominal runs with incomplete requests.

usage: python3 -I audit_tables.py /path/to/ugv-benchmark-public
