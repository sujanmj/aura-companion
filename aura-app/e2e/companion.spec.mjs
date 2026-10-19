import { test, expect } from "@playwright/test";
async function connect(page, suffix = "") {
  await page.goto("/" + suffix);
  await page.getByLabel("Session code").fill("browser-test-session-123456789");
  await page.getByRole("button", { name: "Connect to AURA" }).click();
  await expect(page.getByText("Connected locally")).toBeAttached();
}
test("conversation, memory, feedback and disabled actions work in the browser", async ({
  page,
}) => {
  await connect(page);
  await page
    .getByLabel("Your message")
    .fill("I am nervous about my presentation");
  await page.getByRole("button", { name: "Send ↗" }).click();
  await expect(page.locator(".message.assistant").last()).toBeVisible();
  await page
    .getByRole("button", { name: "Helpful response", exact: true })
    .last()
    .click();
  await expect(page.getByRole("status")).toContainText("Feedback saved");
  await page.screenshot({
    path: "test-results/conversation.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Memory 02" }).click();
  await expect(page.locator(".fact")).not.toHaveCount(0);
  await page.getByRole("button", { name: "Actions 03" }).click();
  await expect(
    page.getByRole("heading", { name: "Actions are switched off." }),
  ).toBeVisible();
});
test("kiosk requires review by default and honors current auto-send consent", async ({
  page,
}) => {
  await page.addInitScript(() => {
    window.SpeechRecognition = class {
      constructor() {
        window.testRecognition = this;
      }
      start() {}
      abort() {}
    };
  });
  await connect(page, "?kiosk=1");
  const autoSend = page.getByRole("checkbox", {
    name: "Send recognized speech automatically",
  });
  await expect(autoSend).not.toBeChecked();
  await page.getByRole("button", { name: "Start listening" }).click();
  const emit = (text) =>
    page.evaluate((value) => {
      const result = [{ transcript: value }];
      result.isFinal = true;
      window.testRecognition.onresult({ resultIndex: 0, results: [result] });
    }, text);
  const chats = [];
  page.on("request", (req) => {
    if (req.url().endsWith("/api/chat")) chats.push(req);
  });
  await emit("Hey AURA I am nervous about my interview");
  await expect(page.getByLabel("Review your message")).toHaveValue(
    "I am nervous about my interview",
  );
  expect(chats).toHaveLength(0);
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect.poll(() => chats.length).toBe(1);
  await expect(page.locator(".kiosk-reply")).toBeVisible();
  await autoSend.check();
  await emit("Hey AURA help me plan tomorrow");
  await expect.poll(() => chats.length).toBe(2);
  await autoSend.uncheck();
  await emit("Hey AURA keep this as a draft");
  await expect(page.getByLabel("Review your message")).toHaveValue(
    "keep this as a draft",
  );
  expect(chats).toHaveLength(2);
  await page.screenshot({ path: "test-results/kiosk.png", fullPage: true });
  await page.reload();
  await expect(autoSend).not.toBeChecked();
});

test("setup distinguishes local availability from live verification", async ({
  page,
}) => {
  await connect(page);
  await page.getByRole("button", { name: "Setup 04" }).click();
  await expect(
    page.getByRole("heading", { name: "Know what is ready." }),
  ).toBeVisible();
  await expect(
    page.getByText("Local rule-based replies.", { exact: false }),
  ).toBeVisible();
  await expect(page.getByText("Disabled. No tool task can run.")).toBeVisible();
  await page.getByRole("button", { name: "Refresh readiness" }).click();
  await expect(
    page.getByText("Available in this local session."),
  ).toBeVisible();
});
