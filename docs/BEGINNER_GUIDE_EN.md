# Beginner's Guide: continuing this project with Codex / WorkBuddy

Date: 2026-11-15 · Audience: **you have flashed a phone before and can enter fastboot, but you do not write code or run experiments** · English version of `BEGINNER_GUIDE_CN.md`

> After reading this you should be able to: restore the project, open an AI tool, say the correct first sentence, complete one low-risk round of collaboration, and know how to recover if something goes wrong.
> You do **not** need C, Linux kernel knowledge, or build commands. That is the AI's job.
> For the full methodology see `offline/13_continuation_playbook.md`; this file is the plain-language on-ramp.

---

## 0. What this project actually is

### 0.1 Flashing vs. what happens here

| | Familiar flashing | This project |
|---|---|---|
| You receive | A finished `ROM.zip` / `boot.img` | Investigation notes + half-finished source code |
| You do | Enter recovery/fastboot, pick a file, flash, boot | Ask the AI to change code -> rebuild a new `boot.img` -> flash -> read logs -> find why it failed -> change one thing |
| On failure | Try another package | You cannot swap packages; you must read the logs and change **one variable** at a time |
| "Done" means | Boots to desktop | Boots to desktop **and** touch/keys/hardware work, with reproducible evidence saved |
| Time | ~15 minutes | ~10–20 min per round, several rounds |

In short: **flashing installs a finished product; here the product was paused mid-development and you are resuming the build.**

### 0.2 Two separate routes — do not mix them

```
Project
├─ Route A: PREBUILT ROM — stock kernel, build a usable LOS16 ROM
│    Kernel: stock 3.18.71, never compiled from source
│    Result: a flashable ROM zip exists (netdisk category 15_)
│    WiFi fixed; 4 open TODOs: camera, libcurl, diagnostic-code cleanup, sepolicy
│    Continuing = edit ROM config/source -> rebuild system.img -> flash SYSTEM -> test
│
└─ Route B: SELF-COMPILED kernel — build 3.18.120 from source, replace stock kernel
     Kernel: our own 3.18.120
     Result: boots to desktop, touch works after a screen wake; 4 gates still FAIL
     Continuing = edit kernel source/config -> build boot.img -> flash BOOT ONLY -> capture logs -> judge
```

**Images from the two routes are not interchangeable.** `02_/images/boot.img` (stock rollback) and `03_/sys13_system.img` (WiFi-fixed system) are different builds. Before any flash, make the AI state exactly which file goes to which partition.

### 0.3 Actual current state (old reports are misleading)

- The phone is **rolled back to stock**, boots normally, touch and keys work, **not in fastboot**. That is the safe starting point.
- `ROUND*.md` files are an **investigation diary**, not tutorials, and do not describe what the phone is currently running.
- Completion `50/50` measures **whether evidence is complete**, not "half the phone works".
- See `offline/12_ai_handoff_index.md` **section 9** for the authoritative current state.

---

## 1. You only need to do three things

| Only you can | The AI does |
|---|---|
| ① Put the phone into **fastboot manually**, then say "done" | Read logs, compare source, disassemble |
| ② **Tap the screen / press nav keys** when asked, and report honestly | Edit config, write patches, compile, produce boot.img |
| ③ Decide continue / pause / rollback, and approve any file deletion | Run preflight, send flash commands, wait for enumeration, capture evidence, write reports |

**Why fastboot is manual:** on the self-compiled kernel, `adb reboot bootloader` degrades into a normal reboot (an **unfixed** issue in this project). The AI must explicitly say "**please enter fastboot**" and wait for your confirmation. If it starts flashing without that sentence, stop it.

### How to enter fastboot

1. Power off (or let the AI run `adb reboot`, wait for the phone to come back, then power off).
2. Hold **Volume Down**, then press **Power**; release Power at the vibration, keep holding Volume Down until the fastboot screen appears. Use whichever key combo worked for you before.
3. Connect USB.
4. Reply: **"I'm in fastboot"**.
5. The AI handles port check, flashing, reboot, verification.

> Historical lesson: an AI once saw the port online and wrote "device entered fastboot automatically" when a human had done it manually. The rule is now: **never infer, always wait for your confirmation**.

---

## 2. One-time setup

### 2.1 Install

| Tool | Purpose | Where |
|---|---|---|
| **WorkBuddy** or **Codex** | Lets the AI read files, run commands, edit code | Whichever you already use |
| **Git** | Clone the repo | Official installer, or GitHub Desktop |
| **platform-tools** (adb / fastboot) | Talk to the phone | Netdisk `04_9008与刷机工具/platform-tools/` (~11 MiB) |
| **WSL / Ubuntu 20.04** (only for rebuilding Route B) | Compile the kernel | Netdisk `06_WSL重建集/` (1.6 GiB), follow `offline/11_wsl_rebuild_guide.md` route B |
| Extract / checksum | Unpack volumes, verify hashes | 7-Zip or Python 3.14+, plus `sha256sum` |

### 2.2 What to download (you do NOT need all 76 GiB)

Cloud folder `PD1610_Xplay6/` (share link in the README). **Minimum set:**

```
00_必读_恢复说明/      <- download first: checklists, RESTORE, indexes, guides
01_全量冷备分卷/       <- two 973 MiB volumes + manifest.json + SHA256SUMS (authoritative cold copy)
02_原厂回滚与发布包/    <- stock boot.img for recovery
04_9008与刷机工具/      <- adb / fastboot / 9008 programmer
06_WSL重建集/           <- only if you will rebuild the kernel
```

Add per route:
- **Route A**: `03_prebuilt_续修基线/` (sys13 baseline), `15_LOS16_ROM刷机包/` (flashable ROM).
- **Route B**: `01_` already contains the full project; add `06_` for the build environment.

`10_` / `11_` are 40 GiB / 11 GiB raw full-tree archives; only needed to browse old files. **Skip them.**

### 2.3 Two non-negotiable rules

1. **Keep paths identical.** Build scripts hardcode `D:/xplay6/...` and `/home/builder/...`. Restore to the same drive letters and folder names or the build fails with "file not found". Full mapping: `offline/11_wsl_rebuild_guide.md`.
2. **Verify before starting.** Put `SHA256SUMS`, `manifest.json` and both volumes in one folder; have the AI run `sha256sum -c SHA256SUMS`. All **3 lines must say OK**. If not, re-download; never start from a damaged archive.

---

## 3. Your first message to the AI — copy verbatim

### 3.1 WorkBuddy

1. Open WorkBuddy, set the workspace to the repository folder (e.g. `D:/xplay6/github_pd1610`, or the restored project root).
2. Start a new conversation and paste:

```
I'm taking over the PD1610 / Xplay6 kernel project. I'm a flashing user:
I don't write code and I don't run experiments. Please guide me in plain
language, run the commands yourself, and only tell me the actions I must do
physically.

Before starting, read in this order:
1) AGENTS.md (repo root - your hard rules)
2) docs/BEGINNER_GUIDE_EN.md (my plain-language guide)
3) offline/12_ai_handoff_index.md section 9 (authoritative current state)
4) offline/13_continuation_playbook.md (single-variable loop, 8-step SOP)

Do NOT touch the phone and do NOT compile yet. First answer three things:
(1) What state should the phone be in right now, and how do I confirm it?
(2) Am I continuing Route A (ROM) or Route B (self-compiled kernel)? Which
    round do you recommend first, and why?
(3) In this round, which actions require me, and when will you explicitly prompt me?

Rules: report only commands you actually ran and their real output; mark
anything not run as "not executed" with a reproducible command; never infer
that the device entered fastboot by itself; change one variable per round;
always run preflight before flashing.
```

### 3.2 Codex

Codex (CLI or IDE) automatically reads `AGENTS.md` when started in the repo root:

```bash
cd D:/xplay6/github_pd1610      # your actual clone / extraction path
codex
```

Then paste the same opening message. `AGENTS.md` already contains the reading order, single-variable rule, no-fabrication rule, fastboot handshake, boot-only flashing and preflight gate — no need to memorize them.

> If Codex runs in a cloud/sandbox that cannot reach your phone, split the work: let Codex do offline analysis and code changes, then paste the resulting patch/commands into a local WorkBuddy session that can see the device. The round table in section 4 still applies.

### 3.3 Pick a route by appending one of these

**Route A (fix the ROM):**

```
I choose Route A (prebuilt ROM). Read prebuilt/evidence/_log_append4.md and
offline/14_prebuilt_upload_checklist.md first, then tell me which of the 4 open
TODOs is the best first round, which files it needs, and what "flash system,
not boot" means in practice. Do not change anything in round one; give me an
executable plan only.
```

**Route B (fix the kernel):**

```
I choose Route B (self-compiled 3.18.120). Read offline/05_experiment_queue.md
and offline/08_roundA_result.md first, then explain what the A round actually
completed, what the next queued round is, and why capturing evidence beats
changing code. Round one must be zero-risk: status check and evidence only.
```

### 3.4 Three questions to ask at the end of EVERY round

```
Review this round against these three, with evidence for each:
1) What is the sha256 of the input image and its preflight result? Which file?
2) Which exact lines of which file support your PASS/FAIL verdict?
3) Which steps did you NOT execute? Write "not executed" plus a reproducible command.
```

Historical lesson: "input device registered" was once reported as "touch works" while tapping produced zero events. Always demand real numbers (`getevent` line count, IRQ counter delta).

---

## 4. What one round looks like (human's script)

| AI says | You do | You reply |
|---|---|---|
| "I'm checking offline, not touching the phone" | Wait | — |
| "Changed one config line, compiling" | Wait | — |
| "Preflight passed, image sha `xxxx…`. **Please enter fastboot**" | Power off -> Vol Down + Power -> USB -> fastboot screen | **"I'm in fastboot"** |
| "Flash done, rebooting, waiting for adb" | Don't unplug, don't press Power | — |
| "Device may drop once, re-enumerating" | Don't touch; if >2 min, reseat USB and say so | **"I reseated USB"** (if done) |
| "At the desktop. Please tap, swipe, press Back and Recents" | Actually do it | **"Touch: works / dead; Back: dead; Recents: dead"** |
| "0 events captured, this round is FAIL" | That's a valid result | — |
| "Rolling back to stock. **Please enter fastboot**" | Enter fastboot again | **"I'm in fastboot"** |
| "Rollback verified: stock 3.18.71, boots, fastboot exited" | Pick up the phone and confirm | **"Confirmed working"** |

A round takes ~10–20 minutes. The most common hiccup is a USB drop: adb briefly reconnects to the pre-reboot session then disconnects. Let the AI re-enumerate; do not reboot the phone yourself.

---

## 5. Jargon translator (for flashing users)

| Term | Plain meaning |
|---|---|
| `boot.img` | Small package with kernel + ramdisk. Lowest risk. Route B flashes **only** this |
| `system.img` | The whole system partition. Route A flashes this; never confuse with boot.img |
| `fastboot` | Phone mode where the PC writes partitions with the `fastboot` command |
| 9008 / EDL | Qualcomm emergency mode; readable even when the screen is black. Used to see where a bootloop stalls |
| `adb` | USB command/log channel while Android is running |
| `dmesg` | Kernel's own boot diary; the primary source for driver errors |
| `getevent` | Prints every touch and key event. **"Does touch work?" is answered by this, not by eyeballing** |
| input device | A touchscreen/key device the system recognizes. A missing one means no driver |
| I²C / driver binding | Chips on the board need matching drivers; "bound" means paired |
| preflight | Mandatory scripted check before flashing, to refuse obviously broken images |
| single variable | Change one thing per round, otherwise you cannot tell what helped |
| cold boot | Full power-off then power-on (not a reboot). Some bugs only appear here |
| rollback | Reflash stock `boot.img` so the phone is usable again. Done at the end of every round |
| sha256 / hash | Digital fingerprint proving a file is intact and unswapped |
| experiment queue | A to-do table (`offline/05`) with each round's claim, pass criteria and fallback |
| A round result | One real-device round that changed nothing and only captured evidence (`offline/08`) |
| completion meter / gate | 8 weighted acceptance gates. `UNVERIFIED` = "possibly done, no evidence", not "not done" |
| WSL | Linux subsystem inside Windows, needed to build an Android kernel |
| cross-compile | Build a kernel for the phone's CPU on the PC, then produce boot.img |
| patch / diff | Record of which lines changed; safer to ship than an entire source tree |
| `AGENTS.md` | Repo-root rule file written for AIs; Codex reads it automatically |

---

## 6. Safety: when to stop and how to recover

### 6.1 Say "stop and roll back to stock" immediately if

- Stuck on the first/second boot logo for >5 minutes (bootloop).
- Screen stays black, Power does nothing.
- A flash command failed and the AI wants a fourth retry.
- The AI says "I infer the device is already in fastboot" — it must not infer.
- The AI wants to flash `system` / `vendor` / `userdata`, or wipe data / factory reset.

### 6.2 Rollback (AI runs commands, you only enter fastboot)

Stock image: netdisk `02_原厂回滚与发布包/images/boot.img`, sha256 starts `929fda99`.

```
You: power off -> Vol Down + Power -> fastboot -> "I'm in fastboot"
AI:  confirm port -> flash stock boot -> reboot -> wait -> report "3.18.71 / boots"
You: confirm touch and keys -> "Confirmed working"
```

After that the phone is back at the safe starting point; a failed experiment costs nothing.

### 6.3 Eight things never to do

1. Don't flash `system` / `vendor` / `userdata` (unless Route A, explicitly explained and confirmed by you).
2. Don't wipe data / factory reset / format data.
3. Don't set Baidu Netdisk to **two-way sync** — clearing the PC later would delete the cloud copy too. It must be one-way "backup".
4. Don't delete the `.workbuddy/` folder (project memory lives there).
5. Don't unplug USB or press Power while the phone is booting.
6. Don't rename, extract, or edit the two volume files in `01_`.
7. Don't guess on the AI's behalf ("it probably worked") — if the screen doesn't respond, say so.
8. Don't let the AI "fix several things while we're here" — that reliably destroys diagnosability.

---

## 7. How to tell if the AI is making things up

The most expensive mistakes here were **not** bricked phones but **hypotheses written as conclusions** (Round14/15 blamed `usb_bam`; Round16 overturned it). Three hard checks:

| Ask | Good answer | Red flag |
|---|---|---|
| "What's the hash?" | Full sha256 + file path | "Probably about the same as last build" |
| "Where's the evidence?" | `flash_log/roundXX_dmesg.txt` line N, 1266 `getevent` lines | "Logs look fine" with no file |
| "What didn't you run?" | "Not executed: X, command: `...`" | "Everything's done" with no command output |

**[O] vs [H]:** `[O]` = observed fact (log, counter, hash); `[H]` = hypothesis, must be labelled unverified. If you see an `[H]` used as a conclusion, make the AI correct it.

Also: when it says "touch is fixed", the standard follow-up is "how many `getevent` lines, and what was the IRQ delta?" — **device registered ≠ events arriving**. This exact mistake happened in the project.

---

## 8. Recommended first round: no compile, no flash, zero risk

```
This round is zero-risk status verification only. No compile, no flash, no file edits:
1) Confirm the phone is online; read kernel version, boot_completed, input device list.
2) Capture a baseline (dmesg / getprop / input / I2C bindings).
3) Verify local files: repo file count, and sha256sum -c SHA256SUMS (3/3 OK).
4) Give me a plain-language "current state report": what the phone is running,
   where each of the two routes stands, what the next round should be, and what
   you need from me.
Mark anything not executed as "not executed". Do not touch any partition.
```

This tells you whether the AI follows the rules, whether your USB is stable, and whether the downloaded archive is sound — before any real experiment.

---

## 9. FAQ

**I don't know any Linux commands.** You don't need to. The AI runs them and pastes results. You copy the opening message, enter fastboot, tap the screen, and report honestly.

**I can't write C — can I still fix a kernel?** Yes, the AI edits code. Your irreplaceable role is physical device handling and honest feedback. All 26 earlier rounds worked this way.

**The phone looks bricked.** Follow section 6.2 to reflash stock boot. If fastboot is unreachable, 9008 emergency mode still works (tools in netdisk `04_`). A rollback baseline always existed; no irreversible partition writes were made.

**The netdisk link expired / asks for an extraction code.** Ask the maintainer. The README's netdisk index documents the folder structure so you can check completeness.

**The AI says it needs to flash `system` — dangerous?** Route A legitimately flashes `system`; that is a different route from Route B's "boot only" rule. Make it state which file, which partition, and where the rollback copy is, then confirm.

**Does `50/50` mean only half is done?** No. It is an evidence-completeness score after `UNVERIFIED` reached zero. The 4 remaining FAILs are concrete features (cold-boot touch, nav keys, input 5/9, I²C 4/9), not "half the code is missing".

---

## 10. Reading order if you want to go deeper

```
docs/BEGINNER_GUIDE_EN.md (you are here)
   -> AGENTS.md ........................ hard rules for the AI
   -> offline/12_ai_handoff_index.md §9 . where things are, current state
   -> offline/13_continuation_playbook.md  the loop, 6 rules, 8-step SOP, prompts
   -> offline/05_experiment_queue.md ..... rounds A-D with criteria
   -> offline/08_roundA_result.md ........ most recent full device round
   -> ROUND10-19*.md / flash_log/ ....... raw per-round evidence
   -> offline/11_wsl_rebuild_guide.md .... only when rebuilding the toolchain
```

**One sentence to remember:** you own the phone and the verdict; the AI owns the code and the evidence; one variable per round, evidence every round, rollback at the end.
