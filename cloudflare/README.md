# Cloudflare Pages + R2 setup (catalog-test)

This setup publishes only `index.html` through Pages. Inventory, its modified-time label, the photo manifest, and photographs live in R2. A Pages Function serves public reads and accepts uploads only when a private bearer token matches the Worker secret.

## Cloudflare resources

1. Create an R2 bucket named `catalog-assets` (or choose another name and use it consistently below).
2. Install the prepared code changes in the repository and push them through GitHub Desktop. Do not connect Pages to a branch that lacks the `dist/` build and `functions/` files; the current repository root contains inventory and photos.
3. In **Workers & Pages**, create a Pages project from the GitHub repository `concordaldon1/catalog-test`, production branch `main`.
4. Use build command `python3 scripts/build_site.py`, build output directory `dist`, and root directory `/`.
5. In **Settings → Bindings**, add an R2 bucket binding named `CATALOG_BUCKET` pointing to the bucket. Save and redeploy for the binding to take effect.
6. After the first Pages deployment, open PowerShell in the repository and run `py -3 cloudflare_configure.py`. Enter the production `pages.dev` URL. The script saves local settings outside the repository and prints a random token.
7. In **Settings → Variables and Secrets**, add a secret named `CATALOG_UPLOAD_TOKEN` and paste that token. Save and redeploy.
   For a separate RFMS-only admin uploader, add another secret named `CATALOG_INVENTORY_UPLOAD_TOKEN` and share that token privately. The Pages Function accepts it only for `/admin/inventory`; it cannot upload photos or change the photo manifest. Deploy the function code before using this token.
8. Copy `cloudflare_publish.py` and `cloudflare/photo_sync_r2.py` into the Desktop Photo Sync folder; rename `photo_sync_r2.py` to `photo_sync.py`. Keep its existing `photo_sync_config.json` and `Run Photo Sync.bat`.
9. Upload the current inventory by running `Update Inventory.bat`. Upload current photos by running `Run Photo Sync.bat`. Both programs ask before publishing.

Do not enable public access on the bucket. Reads go through the Pages Function, which makes the catalog data public while keeping direct bucket access disabled.

## First publication

The first photo sync uploads every supported image directly inside the configured Google Drive Photos folder. Later syncs hash local files and upload only new or changed images. It retains existing R2 photo names in the manifest and does not delete R2 objects. The inventory updater backs up the prior inventory and timestamp in R2 before replacing them.

## Publishing path

- Catalog code changes go to GitHub and deploy through Pages integration.
- Inventory updates keep the existing RFMS filtering, validation, confirmation, timestamp, and local backup flow, then upload the approved CSV and date label to R2.
- Photo sync uploads new/changed images and writes the manifest last. It does not delete images from R2.
- The upload token belongs only in the local desktop configuration and the Cloudflare secret setting. If it is exposed, replace it in both places.
- The original `update_inventory_github.py` remains available, but it publishes to GitHub. Use `update_inventory.py` for the Cloudflare workflow.

## Free-tier note

Pages serves the static site, and the Pages Function reads objects from R2. Cloudflare's current free limits and pricing can change; check the account's usage/billing page after launch, especially if traffic grows.
