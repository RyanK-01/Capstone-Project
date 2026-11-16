import withSerwistInit from "@serwist/next";

const withSerwist = withSerwistInit({
    swSrc: "app/sw.ts",
    swDest: "public/sw.js",

    // Register the service worker through our own component.
    register: false,

    // Avoid service-worker caching during development.
    disable: process.env.NODE_ENV === "development",

    additionalPrecacheEntries: [
        {
            url: "/~offline",
            revision: "offline-v1",
        },
    ],
});

const nextConfig = {
    output: "standalone",
    experimental: {
        instrumentationHook: true,
    },
};

export default withSerwist(nextConfig);
