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
  await expect(page.locator(".kiosk-reply")).toHaveText(/\S+/);
  await expect(page.locator(".presence")).toHaveAttribute("aria-busy", "false");
  await autoSend.check();
  await emit("Hey AURA help me plan tomorrow");
  await expect.poll(() => chats.length).toBe(2);
  await expect(page.locator(".presence")).toHaveAttribute("aria-busy", "false");
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
  await expect(
    page.getByRole("button", { name: "Test configured provider" }),
  ).toBeDisabled();
  await expect(
    page.getByText(/sends only “Reply with exactly: AURA connection confirmed\.”/),
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
  const conversationCheck = page.getByRole("checkbox", {
    name: "Check a real conversation",
  });
  await expect(conversationCheck).not.toBeChecked();
  await expect(
    page.getByText("These boxes are manual notes saved only in this browser"),
  ).toBeVisible();
  await conversationCheck.check();
  await page.reload();
  await page.getByRole("button", { name: "Setup 04" }).click();
  await expect(
    page.getByRole("checkbox", { name: "Check a real conversation" }),
  ).toBeChecked();
  await page.getByRole("button", { name: "Clear checklist notes" }).click();
  await expect(
    page.getByRole("checkbox", { name: "Check a real conversation" }),
  ).not.toBeChecked();
});

test("browser speech voice and pace are local and persist after reload", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(window.speechSynthesis, "getVoices", {
      value: () => [
        {
          voiceURI: "aura-test-en",
          name: "AURA Test Voice",
          lang: "en-US",
          localService: true,
          default: true,
        },
      ],
    });
    Object.defineProperty(window, "SpeechSynthesisUtterance", {
      value: class {
        rate = 1;
        voice = null;
        onend = null;
        onerror = null;
      },
    });
    window.auraSpeechResult = null;
    Object.defineProperty(window.speechSynthesis, "speak", {
      value: (utterance) => {
        window.auraSpeechResult = {
          rate: utterance.rate,
          voiceURI: utterance.voice?.voiceURI || "",
        };
        queueMicrotask(() => utterance.onend?.());
      },
    });
  });
  await connect(page);
  await page.getByRole("button", { name: "Setup 04" }).click();
  await page.getByLabel("Installed browser voice").selectOption("aura-test-en");
  const pace = page.locator("#browser-voice-rate");
  await pace.focus();
  await pace.press("Home");
  for (let index = 0; index < 7; index++) {
    await page.keyboard.press("ArrowRight");
  }
  await expect(page.getByLabel("Browser speaking pace (1.15×)")).toHaveValue(
    "1.15",
  );
  await page.reload();
  await page.getByRole("button", { name: "Setup 04" }).click();
  await expect(page.getByLabel("Installed browser voice")).toHaveValue(
    "aura-test-en",
  );
  await expect(page.getByLabel("Browser speaking pace (1.15×)")).toHaveValue(
    "1.15",
  );
  await page.getByRole("button", { name: "Conversation 01" }).click();
  await page.getByLabel("Speak replies").check();
  await page.getByLabel("Your message").fill("Say this using my chosen voice");
  await page.getByRole("button", { name: "Send ↗" }).click();
  await expect(page.locator(".message.assistant").last()).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => window.auraSpeechResult))
    .toEqual({ rate: 1.15, voiceURI: "aura-test-en" });
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
  const people = page.getByRole("heading", { name: "People" }).locator("..");
  await expect(people).toContainText("No people have been added to memory.");
  await expect(people).toContainText(
    "This is a manual name memory; face recognition is not enabled.",
  );
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

test("people are added only with recorded consent and can be forgotten", async ({
  page,
}) => {
  await connect(page);
  await page.getByRole("button", { name: "Memory 02" }).click();
  await page.getByLabel("Name", { exact: true }).fill("Maya");
  await page.getByLabel("Relationship (optional)").fill("friend");
  const add = page.getByRole("button", { name: "Add person" });
  await expect(add).toBeDisabled();
  await page.getByLabel("They agreed that AURA may remember their name.").check();
  await add.click();
  const person = page.locator(".fact").filter({ hasText: "Maya" });
  await expect(person).toBeVisible();
  await expect(person).toContainText("friend");
  page.once("dialog", (dialog) => {
    expect(dialog.message()).toContain("associated timeline");
    void dialog.accept();
  });
  await person.getByRole("button", { name: "Forget person" }).click();
  await expect(page.getByRole("status")).toContainText("Person forgotten");
  await expect(person).toHaveCount(0);
});

test("daily reminders require opt-in and can be deleted", async ({ page }) => {
  await connect(page);
  await page.getByRole("button", { name: "Memory 02" }).click();
  await page.getByLabel("What should AURA remind you about?").fill("Stretch");
  await page.getByLabel("Local reminder time").fill("21:00");
  const add = page.getByRole("button", { name: "Add daily reminder" });
  await expect(add).toBeDisabled();
  await page.getByLabel("Enable this daily reminder on this Mac.").check();
  await add.click();
  const reminder = page.locator(".fact").filter({ hasText: "Stretch" });
  await expect(reminder).toContainText("21:00 local time");
  await expect(
    page.getByText("A reminder is not confirmation that you completed the task or took a dose."),
  ).toBeVisible();
  await reminder.getByRole("button", { name: "Pause reminder" }).click();
  await expect(reminder).toContainText("paused");
  await expect(page.getByRole("status")).toContainText("Daily reminder paused");
  await reminder.getByRole("button", { name: "Enable reminder" }).click();
  await expect(reminder).toContainText("active");
  await expect(page.getByRole("status")).toContainText("Daily reminder enabled");
  page.once("dialog", (dialog) => {
    expect(dialog.message()).toContain("Delete the daily reminder");
    void dialog.accept();
  });
  await reminder.getByRole("button", { name: "Delete reminder" }).click();
  await expect(page.getByRole("status")).toContainText("Daily reminder deleted");
  await expect(reminder).toHaveCount(0);
});

test("camera context observations can be deleted from saved memory", async ({
  page,
}) => {
  await connect(page);
  const ambient = await page.evaluate(async () => {
    const response = await fetch("/api/ambient", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: "Hey AURA, are you there?",
        observation: "Local camera context: laptop, person present",
      }),
    });
    return { status: response.status, body: await response.json() };
  });
  expect(ambient.status).toBe(200);
  await page.reload();
  await page.getByRole("button", { name: "Memory 02" }).click();
  const observation = page
    .locator(".fact")
    .filter({ hasText: "Local camera context: laptop, person present" });
  await expect(observation).toBeVisible();
  page.once("dialog", (dialog) => {
    expect(dialog.message()).toContain("Delete this saved observation");
    void dialog.accept();
  });
  await observation.getByRole("button", { name: "Delete observation" }).click();
  await expect(page.getByRole("status")).toContainText("Observation deleted");
  await expect(
    page
      .locator(".fact")
      .filter({ hasText: "Local camera context: laptop, person present" }),
  ).toHaveCount(0);
});

test("saved scene observations can be corrected and become user-authored memory", async ({
  page,
}) => {
  await connect(page);
  const ambient = await page.evaluate(async () => {
    const response = await fetch("/api/ambient", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: "Hey AURA, are you there?",
        observation: "Local camera context: sofa, person present",
      }),
    });
    return response.status;
  });
  expect(ambient).toBe(200);
  await page.reload();
  await page.getByRole("button", { name: "Memory 02" }).click();
  const observation = page
    .locator(".fact")
    .filter({ hasText: "Local camera context: sofa, person present" });
  await expect(observation).toBeVisible();
  await observation.getByRole("button", { name: "Correct" }).click();
  await observation
    .getByLabel("Correct this memory")
    .fill("The blue keys are on the sofa.");
  await page.getByRole("button", { name: "Save correction" }).click();
  await expect(
    page.locator(".fact").filter({ hasText: "User correction: The blue keys are on the sofa." }),
  ).toBeVisible();
  await expect(page.getByRole("status")).toContainText("Observation corrected");
  const status = await page.evaluate(async () => (await (await fetch("/api/status")).json()));
  expect(status.observations[0].source).toBe("user_correction");
});

test("all observation notes can be cleared while other memories remain", async ({
  page,
}) => {
  await connect(page);
  await page.getByLabel("Your message").fill("I am nervous about my presentation");
  await page.getByRole("button", { name: "Send ↗" }).click();
  await expect(page.locator(".message.assistant").last()).toBeVisible();
  await page
    .getByLabel("Your message")
    .fill("Hey AURA, remember that I left the keys by the sofa.");
  await page.getByRole("button", { name: "Send ↗" }).click();
  await expect(page.locator(".message.assistant").last()).toBeVisible();
  const before = await page.evaluate(async () => (await (await fetch("/api/status")).json()));
  expect(before.observations.length).toBeGreaterThan(0);
  expect(before.facts.length).toBeGreaterThan(0);

  await page.getByRole("button", { name: "Memory 02" }).click();
  page.once("dialog", (dialog) => {
    expect(dialog.message()).toContain("Delete all saved observations and explicit event notes");
    expect(dialog.message()).toContain("Facts, people, routines, reminders, and conversations will remain");
    void dialog.accept();
  });
  await page.getByRole("button", { name: "Clear all observations" }).click();
  await expect(page.getByRole("status")).toContainText("Saved observations cleared");
  const after = await page.evaluate(async () => (await (await fetch("/api/status")).json()));
  expect(after.observations).toEqual([]);
  expect(after.facts).toEqual(before.facts);
  expect(after.conversations.length).toBe(before.conversations.length);
});

test("conversation history can be cleared while saved memory remains", async ({
  page,
}) => {
  await connect(page);
  await page
    .getByLabel("Your message")
    .fill("I am nervous about my presentation");
  await page.getByRole("button", { name: "Send ↗" }).click();
  await expect(page.locator(".message.assistant").last()).toBeVisible();
  await page.getByRole("button", { name: "Memory 02" }).click();
  const clearButton = page.getByRole("button", {
    name: "Clear conversation history",
  });
  const beforeDismiss = await page.evaluate(
    async () => await (await fetch("/api/status")).json(),
  );
  expect(beforeDismiss.conversations.length).toBeGreaterThan(0);
  expect(beforeDismiss.facts.length).toBeGreaterThan(0);
  page.once("dialog", (dialog) => {
    expect(dialog.message()).toContain(
      "Saved facts, routines, and observations will remain",
    );
    void dialog.dismiss();
  });
  await clearButton.click();
  const afterDismiss = await page.evaluate(
    async () => (await (await fetch("/api/status")).json()).conversations,
  );
  expect(afterDismiss).toHaveLength(beforeDismiss.conversations.length);
  page.once("dialog", (dialog) => void dialog.accept());
  await clearButton.click();
  await expect(page.getByRole("status")).toContainText(
    "Conversation history cleared",
  );
  await expect
    .poll(async () =>
      page.evaluate(
        async () =>
          (await (await fetch("/api/status")).json()).conversations.length,
      ),
    )
    .toBe(0);
  const afterClear = await page.evaluate(
    async () => await (await fetch("/api/status")).json(),
  );
  expect(afterClear.facts).toEqual(beforeDismiss.facts);
  await page.getByRole("button", { name: "Conversation 01" }).click();
  await expect(
    page
      .locator(".message.user")
      .filter({ hasText: "nervous about my presentation" }),
  ).toHaveCount(0);
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


test("note expiry previews a change and persists only after confirmation", async ({ page }) => {
  await connect(page);
  await page.getByRole("button", { name: "Memory 02" }).click();
  await page.getByLabel("Expire saved notes after").selectOption("7");
  const dismissed = new Promise(resolve => page.once("dialog", async dialog => { await dialog.dismiss(); resolve(); }));
  await page.getByRole("button", { name: "Review note expiry" }).click();
  await dismissed;
  await expect(page.getByText(/Note expiry: keep until you delete/)).toBeVisible();
  page.once("dialog", dialog => {
    expect(dialog.message()).toContain("Backups and chat history remain");
    void dialog.accept();
  });
  await page.getByRole("button", { name: "Review note expiry" }).click();
  await expect(page.getByRole("status")).toContainText("Note expiry saved");
  await page.reload();
  await page.getByRole("button", { name: "Memory 02" }).click();
  await expect(page.getByText(/Note expiry: 7 days/)).toBeVisible();
});


test("a shared contribution needs fresh agreement and stays out of memory", async ({ page }) => {
  await connect(page);
  await page.getByText("Invite AURA to answer a shared question", { exact: true }).click();
  const question = page.getByLabel("Reviewed shared question");
  await question.fill("What game can we play together?");
  const send = page.getByRole("button", { name: "Invite one contribution" });
  const consent = page.getByLabel("Everyone agrees to send this question to the configured provider.");
  await expect(send).toBeDisabled();
  await consent.check();
  await question.fill("What board game can we play together?");
  await expect(consent).not.toBeChecked();
  await consent.check();
  const before = await page.evaluate(async () => (await (await fetch("/api/status")).json()).conversations);
  await send.click();
  await expect(page.getByText("local · not saved · online sources not checked")).toBeVisible();
  await expect(consent).not.toBeChecked();
  const after = await page.evaluate(async () => (await (await fetch("/api/status")).json()).conversations);
  expect(after).toEqual(before);
  await page.getByRole("button", { name: "Clear shared reply" }).click();
  await expect(page.getByText("local · not saved · online sources not checked")).toHaveCount(0);
});


test("online lookup requires exact-query approval and renders inert attributed excerpts", async ({ page }) => {
  await connect(page);
  let calls = 0;
  await page.route("**/api/online/lookup", async route => {
    calls++;
    expect(route.request().postDataJSON()).toEqual({ query: "Raspberry Pi computers", approved: true });
    await route.fulfill({ json: { query: "Raspberry Pi computers", retrieved_at: "2026-10-29T00:00:00Z", unavailable: 0,
      sources: [{ id: 42, title: "Raspberry Pi", url: "https://en.wikipedia.org/?curid=42",
        excerpt: '<img src=x onerror="window.injectionRan=true">Test source text.', truncated: false, ambiguous: false }] } });
  });
  await page.getByText("Check an online source", { exact: true }).click();
  const query = page.getByLabel("Query to send to Wikipedia");
  const approval = page.getByLabel("Approve this exact Wikipedia query.");
  const submit = page.getByRole("button", { name: "Look up approved query" });
  await query.fill("Raspberry Pi");
  await expect(submit).toBeDisabled();
  await approval.check();
  await query.fill("Raspberry Pi computers");
  await expect(approval).not.toBeChecked();
  expect(calls).toBe(0);
  await approval.check();
  await submit.click();
  await expect(page.getByRole("region", { name: "Online source results" })).toContainText("not independently verified facts");
  await expect(page.getByRole("link", { name: "Raspberry Pi — Wikipedia" })).toHaveAttribute("href", "https://en.wikipedia.org/?curid=42");
  expect(await page.evaluate(() => window.injectionRan)).toBeUndefined();
  await expect(approval).not.toBeChecked();
  await expect(submit).toBeDisabled();
  await page.screenshot({ path: "test-results/online-lookup.png", fullPage: true });
  await page.getByRole("button", { name: "Clear online results" }).click();
  await expect(page.getByRole("region", { name: "Online source results" })).toHaveCount(0);
});


test("online cancellation clears approval and does not display a late answer", async ({ page }) => {
  await connect(page);
  let release;
  const released = new Promise(resolve => { release = resolve; });
  await page.route("**/api/online/lookup", async route => {
    await released;
    await route.fulfill({ json: { query: "test", retrieved_at: "2026-10-29T00:00:00Z", sources: [], unavailable: 0 } }).catch(() => {});
  });
  await page.getByText("Check an online source", { exact: true }).click();
  await page.getByLabel("Query to send to Wikipedia").fill("test");
  await page.getByLabel("Approve this exact Wikipedia query.").check();
  const sent = page.waitForRequest("**/api/online/lookup");
  await page.getByRole("button", { name: "Look up approved query" }).click();
  await sent;
  await page.getByRole("button", { name: "Cancel lookup" }).click();
  release();
  await expect(page.getByRole("status")).toContainText("query may already have reached Wikipedia");
  await expect(page.getByRole("region", { name: "Online source results" })).toHaveCount(0);
  await expect(page.getByLabel("Approve this exact Wikipedia query.")).not.toBeChecked();
});
