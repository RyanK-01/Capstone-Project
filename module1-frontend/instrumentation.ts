export async function register() {
  if (
    process.env.NEXT_RUNTIME === "nodejs" &&
    process.env.NODE_ENV === "development" &&
    process.env.NEXT_PUBLIC_USE_MOCKS === "true"
  ) {
    const { server } = await import("./mocks/server");

    server.listen({
      onUnhandledRequest: "bypass",
    });

    console.log("[MSW] Node server mocking enabled");
  }
}