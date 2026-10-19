import crypto from "node:crypto";
import express, { Request, Response } from "express";
import dotenv from "dotenv";

dotenv.config();

type TelegramUser = {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
};

type PinRecord = { pin: string; user: TelegramUser; createdAt: number };

const app = express();
app.use(express.json({ limit: "64kb" }));

// In-memory storage keeps the demo self-contained. Pins expire after 15 minutes.
const pins = new Map<string, PinRecord>();
const pinLifetimeMs = 15 * 60 * 1000;

function cleanExpiredPins() {
  const now = Date.now();
  for (const [pin, record] of pins) {
    if (now - record.createdAt > pinLifetimeMs) pins.delete(pin);
  }
}

function hasBotSecret(req: Request) {
  const expected = process.env.BOT_SHARED_SECRET;
  const provided = req.header("x-bot-secret") ?? "";
  if (!expected || provided.length !== expected.length) return false;
  return crypto.timingSafeEqual(Buffer.from(provided), Buffer.from(expected));
}

app.get("/health", (_req, res) => {
  res.status(200).json({ status: "ok" });
});

// The bot calls this endpoint after /start to issue a short-lived login PIN.
app.post("/bot/credentials", (req, res) => {
  if (!hasBotSecret(req)) return res.status(401).json({ error: "Unauthorized" });
  const user = req.body?.user as TelegramUser | undefined;
  if (!user || !Number.isInteger(user.id) || typeof user.first_name !== "string") {
    return res.status(400).json({ error: "A valid Telegram user is required" });
  }

  cleanExpiredPins();
  // Retire prior codes belonging to this Telegram account.
  for (const [pin, record] of pins) {
    if (record.user.id === user.id) pins.delete(pin);
  }

  let pin: string;
  do {
    pin = crypto.randomInt(0, 1_000_000).toString().padStart(6, "0");
  } while (pins.has(pin));

  pins.set(pin, { pin, user, createdAt: Date.now() });
  return res.status(201).json({ key: pin, pin, expires_in: 900 });
});

// auth(key) -> User. The key is the PIN delivered by the Telegram bot.
app.post("/auth", (req, res) => {
  const key = req.body?.key;
  if (typeof key !== "string" || !/^\d{6}$/.test(key)) {
    return res.status(400).json({ error: "Enter the six-digit PIN from the bot" });
  }
  cleanExpiredPins();
  const record = pins.get(key);
  if (!record) return res.status(401).json({ error: "PIN is invalid or expired" });
  pins.delete(key); // One-time use.
  return res.json(record.user);
});

// Telegram sends webhook updates here. Aiogram's webhook service can be placed
// behind this route, or Telegram can be configured directly to /telegram/webhook.
// This route forwards the update to the local Aiogram service when configured.
app.post("/telegram/webhook", async (req, res) => {
  const expected = process.env.BOT_WEBHOOK_SECRET;
  const supplied = req.header("x-telegram-bot-api-secret-token");
  if (expected && supplied !== expected) return res.sendStatus(401);

  const botWebhookTarget = process.env.AIOGRAM_WEBHOOK_URL;
  if (botWebhookTarget) {
    try {
      const result = await fetch(botWebhookTarget, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(req.body),
      });
      return res.sendStatus(result.ok ? 200 : 502);
    } catch {
      return res.sendStatus(502);
    }
  }
  return res.status(501).json({ error: "Configure AIOGRAM_WEBHOOK_URL to forward updates" });
});

const port = Number(process.env.PORT ?? 3000);
app.listen(port, "0.0.0.0", () => {
  console.log(`API listening on http://localhost:${port}`);
});
