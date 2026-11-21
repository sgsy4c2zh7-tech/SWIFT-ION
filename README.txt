SWIFT-ION v0.7 GitHub Actions workflow merge-conflict fix.

1. Extract ZIP.
2. Copy .github/workflows/pages.yml into the SWIFT-ION repository,
   replacing the existing file (which has <<<<<<< / ======= / >>>>>>> conflict markers).
3. Commit: Fix unresolved merge conflict in Pages workflow
4. Push origin and check Actions > Build and publish SWIFT-ION.
5. Check 'Calculate global IRI samples and TEC sensitivity scenarios'
   and 'Validate ionosphere JSON' before checking published site.

This patch fixes YAML syntax only. Real IRI execution and Pages deployment
are not verified until GitHub Actions completes successfully.
