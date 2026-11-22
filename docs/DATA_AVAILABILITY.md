# Text for the manuscript

## Data and code availability statement

The frozen simulator, all experiment code, the prespecified protocols, the complete campaign archives (14,013 validated simulation runs with run-level outputs), the analysis tables and the verification scripts are openly available at https://github.com/SaraSsabila-19/ugv-energy-aware-dispatch (release v1.0.0) and are archived at Zenodo, DOI: 10.5281/zenodo.XXXXXXX. The repository's verification script recomputes every reported contrast from the run-level data. The external road-load measurements used for the sensitivity range are the ESOGU-ML5EV dataset (Polat et al., 2025; DOI 10.5281/zenodo.14912892; Apache-2.0). Road-network geometry is derived from OpenStreetMap (© OpenStreetMap contributors, ODbL).

Replace `XXXXXXX` once Zenodo has minted the DOI for the GitHub release (see below).

## Software citation (reference list)

Salsabila, S. (2026). ugv-energy-aware-dispatch: Reproducibility package for "When does energy-aware online dispatch save energy?" (Version 1.0.0) [Computer software and data]. Zenodo. https://doi.org/10.5281/zenodo.XXXXXXX

## Minting the DOI (one-time, about 5 minutes)

1. Sign in at https://zenodo.org with your GitHub account.
2. Open https://zenodo.org/account/settings/github/ and switch on `ugv-energy-aware-dispatch`. The repository must be public for Zenodo to archive it; reviewers also need it public, or need a private-sharing arrangement.
3. On GitHub, create a release: Releases → Draft a new release, tag `v1.0.0`, title `v1.0.0 – submission version`, then publish.
4. Zenodo archives the release automatically and shows the DOI. Put that DOI in this file, in `CITATION.cff` (`doi:`) and in the manuscript.

## Generative AI disclosure (suggested wording, adapt as required by the journal)

During the preparation of this work the author used AI assistants for experiment-kit engineering, code review, statistical checking and language editing. All simulation runs, results and verification outputs are archived and reproducible from this repository. The author reviewed and edited all content and takes full responsibility for the publication.
