/* Yalnızca uygulama kabuğunu (statik dosyalar) önbelleğe alır; API yanıtları ASLA önbelleğe alınmaz. */
const SURUM = "pansiyon-izin-v1";
const KABUK = [
  "/", "/static/style.css", "/static/form.css", "/static/util.js", "/static/form.js", "/static/app.js",
  "/static/vendor/qrcode.js", "/static/vendor/jsQR.js", "/manifest.webmanifest",
  "/static/icons/icon-192.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SURUM).then((c) => c.addAll(KABUK)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((anahtarlar) =>
    Promise.all(anahtarlar.filter((a) => a !== SURUM).map((a) => caches.delete(a))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  const statik = url.pathname === "/" || url.pathname.startsWith("/static/") || url.pathname === "/manifest.webmanifest";
  if (!statik) return; // API ve diğer her şey doğrudan ağa gider

  // Önce ağ (güncel kalsın), ağ yoksa önbellek
  e.respondWith(fetch(e.request).then((yanit) => {
    if (yanit.ok) { const kopya = yanit.clone(); caches.open(SURUM).then((c) => c.put(e.request, kopya)); }
    return yanit;
  }).catch(() => caches.match(e.request)));
});
