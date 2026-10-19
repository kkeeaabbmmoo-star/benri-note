const V='benri-v1.0.1';
const SHELL='benri-shell-'+V, DATA='benri-data-'+V;
const ASSETS=['./','index.html','manifest.webmanifest','icon-180.png','icon-192.png','icon-512.png'];
self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(SHELL).then(c=>c.addAll(ASSETS)))});
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==SHELL&&k!==DATA).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(e.request.method!=='GET'||u.origin!==location.origin)return;
  const isData=u.pathname.includes('/data/'), cn=isData?DATA:SHELL, key=isData?u.origin+u.pathname:e.request;
  // network-first for everything (data always fresh); offline falls back to cache
  e.respondWith(fetch(e.request,{cache:'no-store'}).then(r=>{if(r.ok){const cp=r.clone();caches.open(cn).then(c=>c.put(key,cp))}return r})
    .catch(()=>caches.match(key,{ignoreSearch:true}).then(r=>r||caches.match('index.html'))))});
