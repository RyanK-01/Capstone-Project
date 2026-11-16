import type {
    PrecacheEntry,
    SerwistGlobalConfig,
} from "serwist";

import {
    ExpirationPlugin,
    NetworkFirst,
    NetworkOnly,
    Serwist,
    StaleWhileRevalidate,
} from "serwist";

declare global {
    interface WorkerGlobalScope extends SerwistGlobalConfig {
        __SW_MANIFEST: (PrecacheEntry | string)[] | undefined;
    }
}

declare const self: ServiceWorkerGlobalScope;

// Only include pages whose HTML is safe to store on the device.
// Add other public, non-sensitive routes as appropriate.
const CACHEABLE_PAGE_PATHS = new Set([
    "/login",
    "/register",
    "/sessions"
]);

const serwist = new Serwist({
    precacheEntries: self.__SW_MANIFEST,

    skipWaiting: true,
    clientsClaim: true,
    navigationPreload: true,

    runtimeCaching: [
        // Never cache API responses, including authenticated GET requests.
        {
            matcher: ({ sameOrigin, url }) =>
                sameOrigin && url.pathname.startsWith("/api/"),
            handler: new NetworkOnly(),
        },

        // Prefer the network for public pages, falling back to cache offline.
        {
            matcher: ({ request, sameOrigin, url }) =>
                sameOrigin &&
                request.mode === "navigate" &&
                CACHEABLE_PAGE_PATHS.has(url.pathname),

            handler: new NetworkFirst({
                cacheName: "saiv-public-pages",
                networkTimeoutSeconds: 3,
                plugins: [
                    new ExpirationPlugin({
                        maxEntries: 10,
                        maxAgeSeconds: 24 * 60 * 60,
                    }),
                ],
            }),
        },

        // Keep static resources available and refresh them in the background.
        {
            matcher: ({ request, sameOrigin }) =>
                sameOrigin &&
                ["script", "style", "font", "image"].includes(
                    request.destination
                ),

            handler: new StaleWhileRevalidate({
                cacheName: "saiv-static-resources",
                plugins: [
                    new ExpirationPlugin({
                        maxEntries: 100,
                        maxAgeSeconds: 7 * 24 * 60 * 60,
                    }),
                ],
            }),
        },
    ],

    fallbacks: {
        entries: [
            {
                url: "/~offline",
                matcher({ request }) {
                    return request.destination === "document";
                },
            },
        ],
    },
});

serwist.addEventListeners();