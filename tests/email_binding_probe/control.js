export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (env.PROBE_MODE !== "local-only" || url.hostname !== "127.0.0.1") {
      return Response.json({ stage: "refused" }, { status: 404 });
    }
    if (request.method === "GET" && url.pathname === "/health") {
      return Response.json({ stage: "healthy" });
    }
    if (request.method !== "POST" || url.pathname !== "/probe") {
      return Response.json({ stage: "refused" }, { status: 404 });
    }
    try {
      await env.EMAIL.send({
        from: "sender@example.invalid",
        to: "mailbox@example.invalid",
        subject: "Local simulator probe",
        text: "Synthetic local-only content.",
      });
      return Response.json({ stage: "send-accepted" });
    } catch (error) {
      return Response.json({ stage: "send", error_type: error.name }, { status: 500 });
    }
  },
};
