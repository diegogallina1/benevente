import { applyBaseHeaders, hasAllowedOrigin, isRateLimited } from "./_guard.js";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Trim, cap the length, and replace every control character with a space.
 *
 * The subject line is assembled from user input and a newline inside a header
 * field is the classic way to append a header of your own. The filter compares
 * code points rather than using a character class, so no control character has
 * to appear in this source file, where a reviewer could not see it.
 */
function clean(value, limit) {
  let output = "";
  for (const character of String(value || "")) {
    const code = character.codePointAt(0);
    output += code < 0x20 || code === 0x7f ? " " : character;
  }
  return output.trim().slice(0, limit);
}

export default async function handler(request, response) {
  applyBaseHeaders(response);
  if (request.method !== "POST") {
    response.setHeader("Allow", "POST");
    return response.status(405).json({ error: "Método não permitido." });
  }
  if (!hasAllowedOrigin(request)) {
    return response.status(403).json({ error: "Origem não autorizada." });
  }
  // Sending mail costs money and sender reputation. Five per hour per address
  // is far above any honest use of a demonstration form.
  if (isRateLimited(request, { limit: 5, windowMs: 60 * 60 * 1000, name: "demo" })) {
    response.setHeader("Retry-After", "3600");
    return response.status(429).json({ error: "Muitas solicitações. Tente novamente mais tarde." });
  }
  const name = clean(request.body?.name, 120);
  const email = clean(request.body?.email, 180);
  const institution = clean(request.body?.institution, 180);
  const useCase = clean(request.body?.use_case, 100);
  const message = clean(request.body?.message, 2000);
  if (!name || !EMAIL.test(email) || !institution || !message) {
    return response.status(400).json({ error: "Preencha nome, e-mail profissional, instituição e necessidade." });
  }
  if (!process.env.RESEND_API_KEY || !process.env.BENEVENTE_CONTACT_EMAIL || !process.env.BENEVENTE_FROM_EMAIL) {
    return response.status(503).json({ error: "O canal comercial ainda não foi configurado. Solicite à equipe a ativação do contato institucional." });
  }
  const emailResponse = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${process.env.RESEND_API_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      from: process.env.BENEVENTE_FROM_EMAIL,
      to: [process.env.BENEVENTE_CONTACT_EMAIL],
      reply_to: email,
      subject: `[Benevente] Solicitação de demonstração — ${institution}`,
      text: `Nome: ${name}\nE-mail: ${email}\nInstituição: ${institution}\nPerfil de uso: ${useCase}\n\nNecessidade:\n${message}`,
    }),
  });
  if (!emailResponse.ok) {
    // The upstream body can echo the recipient address; log the status only.
    console.error("Lead email delivery failed", emailResponse.status);
    return response.status(502).json({ error: "Não foi possível encaminhar a solicitação agora. Tente novamente." });
  }
  return response.status(200).json({ ok: true });
}
