# Public profile metrics

`python3 scripts/update_profile.py --write` refreshes the two activity panels used by the profile README. `--check` reports whether refreshing is necessary without writing files.

The workflow runs daily at 09:17 America/Fortaleza (12:17 UTC), on relevant pushes, and on manual dispatch. It uses GitHub's public user-repositories endpoint with complete pagination. Only public, owned, non-fork projects count; the profile repository is excluded. Archived projects count toward totals, but the three recent entries exclude archived and unpushed repositories. Dates use America/Fortaleza.

The fetch and both rendered outputs must succeed before writing. A provider failure preserves the last valid panels. The workflow commits only the two activity SVGs, using its repository-scoped `GITHUB_TOKEN`.

The SVGs use outlined glyphs so the approved typography does not depend on fonts installed on GitHub or on a reader's computer. `profile-glyphs.json` contains the regular and bold Manrope outlines needed for repository names, numbers and dates. It is distributed under the [SIL Open Font License](../assets/lex-profile/Manrope-OFL.txt); upstream: [Manrope](https://github.com/googlefonts/manrope). Runtime generation uses only Python's standard library.

Each dynamic group stores its anchor, size, face and color. Refreshes replace only the groups with known metric IDs and update the accessible title, description and labels. The remaining artwork stays unchanged. All project banners and the other SVGs are static assets.
