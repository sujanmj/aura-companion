import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
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
  await expect(page.getByRole("heading", { name: "Routines" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Recent observations" }),
  ).toBeVisible();
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
  await expect(
    page.getByRole("heading", { name: "Companion check-ins" }),
  ).toBeVisible();
  await expect(page.getByLabel("Allow AURA to check in")).not.toBeChecked();
  await expect(page.getByLabel("Quiet hours start")).toHaveValue("22:00");
  await expect(page.getByLabel("Quiet hours end")).toHaveValue("08:00");
  await page.getByLabel("Allow AURA to check in").check();
  await page.getByRole("button", { name: "Save check-in preferences" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Check-in preferences saved",
  );
  await page.reload();
  await page.getByRole("button", { name: "Setup 04" }).click();
  await expect(page.getByLabel("Allow AURA to check in")).toBeChecked();
});

test("saved facts can be corrected and forgetting requires confirmation", async ({
  page,
}) => {
  await connect(page);
  await page
    .getByLabel("Your message")
    .fill("I am nervous about my presentation");
  await page.getByRole("button", { name: "Send ↗" }).click();
  await expect(page.locator(".message.assistant").last()).toBeVisible();
  await page.getByRole("button", { name: "Memory 02" }).click();
  const fact = page.locator(".fact").filter({ hasText: "recent anxiety" });
  await expect(fact).toBeVisible();
  await fact.getByRole("button", { name: "Correct" }).click();
  await fact
    .getByLabel("Correct what AURA remembers")
    .fill("I prefer a calm check-in, not assumptions.");
  await fact.getByRole("button", { name: "Save correction" }).click();
  await expect(
    page
      .locator(".fact")
      .filter({ hasText: "I prefer a calm check-in, not assumptions." }),
  ).toBeVisible();
  let dialogMessage = "";
  page.once("dialog", (dialog) => {
    dialogMessage = dialog.message();
    void dialog.dismiss();
  });
  await page
    .locator(".fact")
    .filter({ hasText: "recent anxiety" })
    .getByRole("button", { name: "Forget" })
    .click();
  expect(dialogMessage).toContain(
    "Your original messages remain in chat history",
  );
  await expect(
    page
      .locator(".fact")
      .filter({ hasText: "I prefer a calm check-in, not assumptions." }),
  ).toBeVisible();
  page.once("dialog", (dialog) => void dialog.accept());
  await page
    .locator(".fact")
    .filter({ hasText: "recent anxiety" })
    .getByRole("button", { name: "Forget" })
    .click();
  await expect(
    page.locator(".fact").filter({ hasText: "recent anxiety" }),
  ).toHaveCount(0);
  await expect(page.getByRole("status")).toContainText("Memory forgotten");
  await page.getByRole("button", { name: "Conversation 01" }).click();
  await page
    .getByLabel("Your message")
    .fill("I am nervous about my presentation again");
  await page.getByRole("button", { name: "Send ↗" }).click();
  await expect(page.locator(".message.assistant").last()).toBeVisible();
  await page.getByRole("button", { name: "Memory 02" }).click();
  await expect(
    page.locator(".fact").filter({ hasText: "recent anxiety" }),
  ).toHaveCount(0);
});

test("saved routines can be corrected and forgotten without automatic recreation", async ({
  page,
}) => {
  await connect(page);
  await page.getByLabel("Your message").fill("I like gym workouts");
  await page.getByRole("button", { name: "Send ↗" }).click();
  await expect(page.locator(".message.assistant").last()).toBeVisible();
  await page.getByRole("button", { name: "Memory 02" }).click();
  const routine = page.locator(".fact").filter({ hasText: "fitness interest" });
  await expect(routine).toBeVisible();
  await routine.getByRole("button", { name: "Correct" }).click();
  await routine.getByLabel("Correct this routine").fill("I prefer swimming.");
  await routine.getByRole("button", { name: "Save correction" }).click();
  await expect(
    page.locator(".fact").filter({ hasText: "I prefer swimming." }),
  ).toBeVisible();
  page.once("dialog", (dialog) => {
    expect(dialog.message()).toContain("will not automatically save it again");
    void dialog.accept();
  });
  await page
    .locator(".fact")
    .filter({ hasText: "I prefer swimming." })
    .getByRole("button", { name: "Forget" })
    .click();
  await expect(page.getByRole("status")).toContainText("Routine forgotten");
  await page.getByRole("button", { name: "Conversation 01" }).click();
  await page.getByLabel("Your message").fill("I like gym workouts");
  await page.getByRole("button", { name: "Send ↗" }).click();
  await expect(page.locator(".message.assistant").last()).toBeVisible();
  await page.getByRole("button", { name: "Memory 02" }).click();
  await expect(
    page.getByRole("heading", { name: "Routines" }).locator(".."),
  ).toContainText("No routines have been saved.");
});

test("memory export downloads the current authenticated account data", async ({
  page,
}) => {
  await connect(page);
  await page
    .getByLabel("Your message")
    .fill("Please remember I like green tea");
  await page.getByRole("button", { name: "Send ↗" }).click();
  await expect(page.locator(".message.assistant").last()).toBeVisible();
  await page.getByRole("button", { name: "Memory 02" }).click();
  const downloadReady = page.waitForEvent("download");
  await page
    .getByRole("link", { name: "Download all my AURA data (JSON)" })
    .click();
  const download = await downloadReady;
  expect(download.suggestedFilename()).toBe("aura-memory-export.json");
  const exported = JSON.parse(await readFile(await download.path(), "utf8"));
  expect(exported.format).toBe("aura-memory-export");
  expect(exported.records.conversation_logs).toContainEqual(
    expect.objectContaining({
      role: "user",
      message: "Please remember I like green tea",
    }),
  );
});
