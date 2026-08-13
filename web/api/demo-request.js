const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const clean = (value, limit) => String(value || "").trim().slice(0, limit);

export default async function handler(request, response) {
  if (request.method !== "POST") {
    response.setHeader("Allow", "POST");
    return response.status(405).json({ error: "Método não permitido." });
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
    console.error("Lead email delivery failed", await emailResponse.text());
    return response.status(502).json({ error: "Não foi possível encaminhar a solicitação agora. Tente novamente." });
  }
  return response.status(200).json({ ok: true });
}
