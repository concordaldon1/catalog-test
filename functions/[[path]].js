const TOKEN_HEADER = "Authorization";
const PHOTO_CACHE_SECONDS = 300;

function jsonResponse(value, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}

function equalToken(a, b) {
  if (!a || !b || a.length !== b.length) return false;
  let mismatch = 0;
  for (let i = 0; i < a.length; i++) mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return mismatch === 0;
}

function objectKeyFromPhotoPath(path) {
  if (!path.startsWith("/photos/")) return null;
  let key;
  try {
    key = decodeURIComponent(path.slice("/photos/".length));
  } catch {
    return null;
  }
  if (!key || key.split("/").some((part) => !part || part === "." || part === "..")) return null;
  return `photos/${key}`;
}

async function publicObject(request, env, ctx, key, contentType, cacheSeconds) {
  const cache = caches.default;
  const cacheRequest = new Request(new URL(request.url).toString(), { method: "GET" });
  if (cacheSeconds > 0) {
    const cached = await cache.match(cacheRequest);
    if (cached) return cached;
  }

  const object = await env.CATALOG_BUCKET.get(key);
  if (!object) return new Response("Not found", { status: 404 });
  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("Content-Type", contentType);
  headers.set("Cache-Control", `public, max-age=${cacheSeconds}`);
  const response = new Response(object.body, { headers });
  if (cacheSeconds > 0) ctx.waitUntil(cache.put(cacheRequest, response.clone()));
  return response;
}

function mimeType(key) {
  const ext = key.toLowerCase().split(".").pop();
  return ({ jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png", webp: "image/webp" })[ext] || "application/octet-stream";
}

export async function onRequest(context) {
  const { request, env, waitUntil } = context;
  const ctx = { waitUntil };
  const url = new URL(request.url);
  const path = url.pathname;

  if (request.method === "GET" && path === "/inventory.csv") {
    return publicObject(request, env, ctx, "inventory.csv", "text/csv; charset=utf-8", 0);
  }
  if (request.method === "GET" && path === "/inventory_date.txt") {
    return publicObject(request, env, ctx, "inventory_date.txt", "text/plain; charset=utf-8", 0);
  }
  if (request.method === "GET" && path === "/photos/manifest.json") {
    return publicObject(request, env, ctx, "photos/manifest.json", "application/json; charset=utf-8", 30);
  }
  if (request.method === "GET" && path.startsWith("/photos/")) {
    const key = objectKeyFromPhotoPath(path);
    if (!key) return new Response("Bad photo path", { status: 400 });
    return publicObject(request, env, ctx, key, mimeType(key), PHOTO_CACHE_SECONDS);
  }

  if (path.startsWith("/admin/")) {
    if (request.method !== "PUT") return new Response("Method not allowed", { status: 405 });
    const provided = request.headers.get(TOKEN_HEADER)?.replace(/^Bearer\s+/i, "") || "";
    if (!equalToken(provided, env.CATALOG_UPLOAD_TOKEN)) return new Response("Unauthorized", { status: 401 });

    if (path === "/admin/inventory") {
      let payload;
      try { payload = await request.json(); } catch { return jsonResponse({ error: "Invalid JSON" }, 400); }
      if (typeof payload.inventory !== "string" || typeof payload.timestamp !== "string") {
        return jsonResponse({ error: "Expected inventory and timestamp strings" }, 400);
      }
      const old = await env.CATALOG_BUCKET.get("inventory.csv");
      if (old) {
        const backupKey = `inventory_backups/inventory_before_${Date.now()}.csv`;
        await env.CATALOG_BUCKET.put(backupKey, old.body, { httpMetadata: { contentType: "text/csv; charset=utf-8" } });
      }
      const oldDate = await env.CATALOG_BUCKET.get("inventory_date.txt");
      if (oldDate) {
        const backupDate = `inventory_backups/inventory_date_before_${Date.now()}.txt`;
        await env.CATALOG_BUCKET.put(backupDate, oldDate.body, { httpMetadata: { contentType: "text/plain; charset=utf-8" } });
      }
      await env.CATALOG_BUCKET.put("inventory.csv", payload.inventory, { httpMetadata: { contentType: "text/csv; charset=utf-8" } });
      await env.CATALOG_BUCKET.put("inventory_date.txt", payload.timestamp, { httpMetadata: { contentType: "text/plain; charset=utf-8" } });
      await caches.default.delete(new Request(new URL("/inventory.csv", url)));
      await caches.default.delete(new Request(new URL("/inventory_date.txt", url)));
      return jsonResponse({ ok: true, backedUp: Boolean(old) });
    }

    if (path === "/admin/manifest") {
      let files;
      try { files = await request.json(); } catch { return jsonResponse({ error: "Invalid JSON" }, 400); }
      if (!Array.isArray(files) || files.some((name) => typeof name !== "string" || !name || name.includes("/") || name.includes("\\"))) {
        return jsonResponse({ error: "Expected an array of root photo filenames" }, 400);
      }
      await env.CATALOG_BUCKET.put("photos/manifest.json", JSON.stringify(files, null, 2) + "\n", {
        httpMetadata: { contentType: "application/json; charset=utf-8" },
      });
      await caches.default.delete(new Request(new URL("/photos/manifest.json", url)));
      return jsonResponse({ ok: true, photos: files.length });
    }

    if (path.startsWith("/admin/photos/")) {
      const key = objectKeyFromPhotoPath(path.replace("/admin/photos/", "/photos/"));
      if (!key || key.endsWith("/manifest.json")) return new Response("Bad photo path", { status: 400 });
      await env.CATALOG_BUCKET.put(key, request.body, { httpMetadata: { contentType: mimeType(key) } });
      await caches.default.delete(new Request(new URL(path.replace("/admin/photos/", "/photos/"), url)));
      return jsonResponse({ ok: true });
    }
    return new Response("Not found", { status: 404 });
  }

  return env.ASSETS.fetch(request);
}
