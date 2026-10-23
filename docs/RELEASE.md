# Local release preparation

The repository is standalone and has no configured publication destination. The user must explicitly approve remote push/public release before either happens.

Before preparing a source ZIP:

```sh
python -m unittest discover -s tests -v
python tools/release_check.py
git status --short
python tools/build_release.py
```

The builder reads Git-tracked source paths only, scans them and generates a local ZIP with a SHA-256 file manifest. It never publishes anything. Local references, replays, analysis packages, binaries and fonts are excluded. Do not distribute the workspace folder or its `.private_reference` directory as a whole.

Fresh-clone rehearsal (uses the current committed HEAD, writes only under ignored dist):

```sh
python tools/fresh_clone_smoke.py
```

After explicit approval and creation of the intended empty repository, the user can replace the placeholder with the actual destination:

```sh
git remote add origin <approved-repository-URL>
git push -u origin main
```

These commands are documentation only and were not run. CI tests/builds source on pushes and pull requests; it has no deployment/release job. Source commits use a generic contributor identity to avoid embedding a personal email in publication metadata.
