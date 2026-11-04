# Phantom Scan — Sponsorship Pitch Script (JODDB)

**Audience:** JODDB decision-makers, telecommunications head engineer, academic supervisor, other attendees
**Goal:** Secure sponsorship/funding support
**Format:** ~15–20 min talk + live hardware demo, bilingual (English / Arabic)
**Prepared:** 2026-07-23

---

## ⚠️ Before you use this script — fill these in

I don't have real information about JODDB's mandate, your funding ask number, your team composition, or your timeline — I only have the repository's code and docs. Do not present this script until you've replaced every `[BRACKET]` below. Presenting invented specifics about JODDB or a funding figure I made up would undermine your credibility with a room that includes a regulator and an engineer who will fact-check you live.

| Placeholder | What to fill in |
|---|---|
| `[JODDB FULL NAME / MANDATE]` | JODDB's actual name and what they regulate/fund, so you can frame relevance correctly |
| `[FUNDING AMOUNT]` | The specific ask — hardware budget, pilot budget, or engineering-time budget |
| `[TIMELINE]` | How long the funded phase would take (e.g., "12 weeks to a calibrated field pilot") |
| `[YOUR NAME / SUPERVISOR NAME / TEAM]` | Credits slide |
| `[PILOT SITE]` | If you have a candidate deployment site in mind |
| `[YOUR BOM COST]` | Confirm actual per-node hardware cost — see note below |

**On the cost figure:** the current README states **~$7 per ESP32-S3 radio**; an older internal draft (`docs/PHANTOM_SCAN_PRELIMINARY_TECHNICAL_DELIVERABLE.md`, marked historical/superseded) says **~$28/node** including enclosure and antenna. Use whichever number you can actually defend if asked for a bill of materials — don't quote $7 as an all-in deployed-node cost unless that's genuinely just the module.

**On scope:** this script is built strictly from what the current README and codebase say the system does *today* — a fixed two-node, 1-D presence/position sensor, real-hardware-unverified for calibrated accuracy. It deliberately does **not** claim UAV integration, multi-person vitals, or 3D pose estimation as current capability — those appear only in an older, explicitly superseded internal draft with unmeasured targets. If you want them in the pitch, present them as *roadmap*, not *proof*. A telecom engineer will ask "show me," and the honest two-node result is what you can actually show.

---

## How to use this bilingual script

Every section gives you the **English** delivery and the **Arabic (MSA)** delivery in full. In practice, most Jordanian technical audiences code-switch naturally — a common and effective pattern for this room:

- **Arabic** for rapport-building moments: the greeting, framing the problem, the ask, the thanks.
- **English** for precise technical terms: protocol names, metrics, architecture — this also matches how your codebase, ADRs, and test output are written, so it'll match what's on your slides/screen.

Pick one language track and stay consistent within a section — switching mid-sentence reads as unrehearsed. Practice the demo section out loud at least twice; it's the part most likely to run long or short depending on hardware cooperation.

---

## Timing map (≈20 min total)

| Time | Segment |
|---|---|
| 0:00–0:45 | Opening & greeting |
| 0:45–2:15 | The problem |
| 2:15–3:30 | The idea, in one sentence |
| 3:30–5:00 | Why this matters to JODDB / telecom |
| 5:00–7:30 | How it works — architecture |
| 7:30–9:00 | Phantom Balance Fusion — the core technical idea |
| 9:00–10:30 | Engineering rigor & honesty |
| 10:30–15:00 | **Live demo** |
| 15:00–16:15 | Current status / where this really stands |
| 16:15–17:30 | Roadmap — what funding unlocks |
| 17:30–18:45 | The ask |
| 18:45–19:30 | Closing & thanks |

---

## 1. Opening & Greeting (0:00–0:45)

**Slide:** Title — "Phantom Scan: Through-Wall Human Presence Sensing from Two $7 Radios" + your name/team.

**EN:**
> Good [morning/afternoon], and thank you for the time. My name is [YOUR NAME], from [TEAM/SUPERVISOR'S LAB]. Today I want to show you something we built that turns ordinary Wi-Fi hardware — the same radios already inside routers and laptops — into a device that can sense a person moving in a room, through a wall, without a camera and without anything worn on the body. I'll explain how it works, show you it running live, and tell you exactly what it can and can't do today — and where [FUNDING AMOUNT] of support would take it next.

**AR:**
> صباح الخير / مساء الخير، وشكرًا لكم على وقتكم. اسمي [YOUR NAME]، من [TEAM/SUPERVISOR'S LAB]. اليوم أود أن أعرض عليكم مشروعًا قمنا بتطويره يحوّل معدات واي-فاي عادية — نفس الرقائق الموجودة في أجهزة الراوتر والحواسيب المحمولة — إلى جهاز قادر على استشعار وجود إنسان يتحرك داخل غرفة، حتى من خلف جدار، دون استخدام كاميرا ودون أي جهاز يُلبَس على الجسم. سأشرح لكم آلية العمل، وسأعرضها أمامكم وهي تعمل فعليًا، وسأكون واضحًا تمامًا حول ما ينجزه النظام اليوم وما لا ينجزه بعد — وأين يمكن لدعم بقيمة [FUNDING AMOUNT] أن يأخذ المشروع للمرحلة القادمة.

---

## 2. The Problem (0:45–2:15)

**Slide:** Three icons — Camera (crossed out), Wearable (crossed out), Blank room — with the question "How do you know someone is there?"

**EN:**
> There's a real gap in how we sense human presence. Cameras work, but they capture faces, biometric data, and raise privacy and legal exposure the moment you point them at a public or semi-public space. Wearables solve privacy, but they only work if the person is compliant — they don't help you sense an intruder, a person trapped in a room, or anyone who simply isn't carrying the device. And traditional motion sensors — PIR, ultrasonic — are cheap but nearly blind through walls and give you almost no information about where the person is or how they're moving.
>
> What's missing is a sensor that's passive, cheap, privacy-preserving by construction — because it never captures an image — and that can see through non-metallic walls. That's the gap Phantom Scan is built to fill.

**AR:**
> توجد فجوة حقيقية في طريقة استشعارنا لوجود الإنسان. الكاميرات فعّالة، لكنها تلتقط الوجوه والبيانات البيومترية، وتثير مخاوف قانونية وخصوصية بمجرد توجيهها نحو أي مساحة عامة أو شبه عامة. الأجهزة القابلة للارتداء تحل مشكلة الخصوصية، لكنها تعمل فقط إن كان الشخص يرتديها فعليًا — فهي لا تفيد في اكتشاف متسلل، أو شخص محاصر داخل غرفة، أو أي شخص لا يحمل الجهاز أصلًا. أما أجهزة الحركة التقليدية — مثل مستشعرات PIR والموجات فوق الصوتية — فهي رخيصة لكنها شبه عمياء عبر الجدران، ولا تعطي معلومات تُذكر عن موقع الشخص أو طريقة حركته.
>
> ما هو مفقود هو مستشعر سلبي، رخيص، يحافظ على الخصوصية بطبيعته — لأنه لا يلتقط أي صورة مطلقًا — وقادر على الرؤية عبر الجدران غير المعدنية. هذه هي الفجوة التي صُمم مشروع Phantom Scan لسدّها.

---

## 3. The Idea, in One Sentence (2:15–3:30)

**Slide:** Router icon → "CSI" waveform → Human silhouette

**EN:**
> Here's the core idea: every Wi-Fi signal that passes through a room is subtly distorted by whatever's in that room — walls, furniture, and people. That distortion is called **Channel State Information**, or CSI, and every modern Wi-Fi chipset already computes it as part of normal operation — it's not something we invented, it's something we're the first to *listen to* for this purpose. When a person moves, their body absorbs and reflects the radio signal in a way that changes CSI in a measurable, repeatable pattern. Phantom Scan reads that pattern from two small radios and turns it into a live position, distance, and movement trend for whoever's in the room — all from signal math, with zero optical sensors.

**AR:**
> الفكرة الأساسية هي التالية: أي إشارة واي-فاي تمر عبر غرفة ما تتأثر بشكل دقيق بكل ما يوجد في تلك الغرفة — الجدران، الأثاث، والأشخاص. هذا التأثير يُسمى **معلومات حالة القناة**، أو CSI، وكل شريحة واي-فاي حديثة تقوم أصلًا بحساب هذه المعلومات كجزء من عملها الطبيعي — نحن لم نخترع هذه البيانات، بل نحن من "يستمع" إليها لهذا الغرض تحديدًا. عندما يتحرك شخص ما، فإن جسده يمتص وينعكس عليه جزء من الإشارة اللاسلكية بطريقة تُغيّر بيانات CSI بنمط قابل للقياس والتكرار. يقرأ Phantom Scan هذا النمط من جهازين لاسلكيين صغيرين، ويحوّله إلى موقع حي، ومسافة، واتجاه حركة لأي شخص داخل الغرفة — كل ذلك اعتمادًا على معالجة رياضية للإشارة، دون أي مستشعر بصري على الإطلاق.

---

## 4. Why This Matters to JODDB / Telecom (3:30–5:00)

**Slide:** "No new spectrum. No new emissions. Just listening."

*(This section is the one most likely to need your input — I've written it around the two facts I'm confident of from the README: (1) the hardware is a standard, commercially available ESP32-S3 Wi-Fi radio, not a custom RF transmitter, and (2) sensing is derived passively from CSI on existing 802.11 traffic. Fill in the bracket with how this maps to JODDB's actual mandate.)*

**EN:**
> I want to speak directly to the telecom engineers in the room, because this is the question you'll ask first: does this need new spectrum or new emissions? No. Phantom Scan runs entirely on standard 2.4 GHz 802.11 Wi-Fi hardware — an ESP32-S3, the same class of radio already inside millions of deployed devices. It doesn't transmit anything a normal Wi-Fi client wouldn't already transmit; the sensing comes from *reading* channel state, not from adding new RF into the environment. That means the compliance and spectrum story is about as simple as it gets — and I believe it's directly relevant to [JODDB FULL NAME / MANDATE]'s mandate because [FILL IN: e.g., "it's a domestically buildable telecom-adjacent sensing technology, using existing licensed-exempt spectrum, that Jordan could develop and export IP for" or "it supports public-safety infrastructure your telecom regulations already govern"].

**AR:**
> أود أن أتوجه مباشرة إلى مهندسي الاتصالات في هذه القاعة، لأن هذا هو السؤال الذي سيُطرح أولًا: هل يحتاج هذا النظام إلى طيف ترددي جديد أو انبعاثات جديدة؟ الجواب لا. يعمل Phantom Scan بالكامل على معدات واي-فاي قياسية بتردد 2.4 جيجاهرتز وفق معيار 802.11 — وهي شريحة ESP32-S3، من نفس فئة الرقائق الموجودة أصلًا في ملايين الأجهزة المنتشرة. النظام لا يُرسل أي شيء لا يرسله جهاز واي-فاي عادي أصلًا؛ فالاستشعار يأتي من "قراءة" حالة القناة، وليس من إضافة إشارات لاسلكية جديدة إلى البيئة. هذا يعني أن قصة الامتثال التنظيمي والطيف الترددي بسيطة قدر الإمكان. وأرى أن هذا مرتبط مباشرة بمهام [JODDB FULL NAME / MANDATE] لأن [FILL IN].

---

## 5. How It Works — Architecture (5:00–7:30)

**Slide:** The five-layer diagram (firmware → ingest → DSP → optional ML → dashboard)

**EN:**
> Let me walk through the system, firmware to browser. Two ESP32-S3 nodes — call them N1 and N2 — sit about three meters apart. Each one captures CSI on-device, timestamps it, and streams it over UDP to a host machine.
>
> That host runs a Node/TypeScript server — this is our single, defined runtime authority, deliberately: we made an explicit architecture decision that only one process is ever allowed to own the live network port, so there's no ambiguity about what's authoritative during a live deployment. That server does deterministic signal processing — amplitude extraction, phase unwrapping, clutter suppression, filtering for breathing-band frequencies, motion energy — no machine learning in that core path. Everything is reproducible math, which matters enormously when you need to explain a result to a regulator or a safety reviewer.
>
> The output streams over WebSocket to a live React dashboard, which I'll show you in a few minutes. There's also an optional AI inference sidecar for future enhancement, but it's isolated by design — the system has to keep working correctly even with that component completely absent.

**AR:**
> اسمحوا لي أن أشرح لكم النظام، من البرمجيات الثابتة وصولًا إلى المتصفح. جهازان من نوع ESP32-S3 — نسمّيهما N1 وN2 — يوضعان على بعد حوالي ثلاثة أمتار عن بعضهما. كل جهاز يلتقط بيانات CSI مباشرة على العتاد، ويضع لها ختم زمني، ثم يرسلها عبر بروتوكول UDP إلى جهاز مضيف.
>
> ذلك الجهاز المضيف يُشغّل خادم Node/TypeScript — وهو السلطة التشغيلية الوحيدة والمحدَّدة للنظام، وهذا قرار معماري متعمّد: قررنا صراحة أن عملية واحدة فقط يُسمح لها بامتلاك منفذ الشبكة الحي، حتى لا يكون هناك أي التباس حول الجهة المرجعية أثناء التشغيل الفعلي. يقوم هذا الخادم بمعالجة إشارة حتمية — استخلاص السعة، فك التفاف الطور، إزالة التشويش الثابت، ترشيح لترددات نطاق التنفس، وطاقة الحركة — دون أي تعلّم آلي في هذا المسار الأساسي. كل شيء هو معالجة رياضية قابلة لإعادة الإنتاج، وهذا أمر بالغ الأهمية عندما تحتاج لشرح نتيجة لجهة تنظيمية أو مراجع سلامة.
>
> يتم بث النتائج عبر WebSocket إلى لوحة تحكم React حية، سأعرضها لكم بعد قليل. يوجد أيضًا وحدة استدلال ذكاء اصطناعي اختيارية لتحسينات مستقبلية، لكنها مصممة لتكون معزولة تمامًا — إذ يجب أن يستمر النظام بالعمل بشكل صحيح حتى في حال غياب هذا المكوّن كليًا.

---

## 6. Phantom Balance Fusion — the Core Technical Idea (7:30–9:00)

**Slide:** N1 —————●—————— N2 line diagram with a moving dot

**EN:**
> Here's the piece I'm proudest of, because it's an honest design choice, not a marketing one. With two nodes, you *cannot* mathematically resolve a true two-dimensional position — that would need a third point of reference. So instead of faking a 2D map, we compute something we call the **cross-node motion ratio**: we measure how much signal disturbance each node sees, and we place the target along the straight line between the two nodes, weighted toward whichever node is sensing more motion. If you're closer to node one, the target slides toward node one. It's a one-dimensional read, and we say so explicitly everywhere in our documentation — because a system that quietly claims 2D precision it doesn't have is a system that will fail a real audit. We'd rather tell you the true, useful thing two radios can do than a false, impressive thing they can't.

**AR:**
> هذا هو الجزء الذي أفتخر به أكثر من غيره، لأنه خيار تصميمي صادق وليس تسويقيًا. باستخدام جهازين فقط، من المستحيل رياضيًا تحديد موقع ثنائي الأبعاد حقيقي — فذلك يتطلب نقطة مرجعية ثالثة. لذلك، بدلًا من تزييف خريطة ثنائية الأبعاد، نقوم بحساب ما نسميه "نسبة الحركة بين العقدتين": نقيس مقدار الاضطراب في الإشارة الذي تلتقطه كل عقدة، ونضع الهدف على الخط المستقيم الواصل بين العقدتين، مع ترجيح باتجاه العقدة التي تستشعر حركة أكبر. إن كنت أقرب للعقدة الأولى، ينزلق الهدف نحوها. هذه قراءة أحادية البُعد، ونذكر ذلك صراحة في كل موضع من توثيقنا — لأن أي نظام يدّعي ضمنيًا دقة ثنائية الأبعاد لا يمتلكها هو نظام سيفشل في أي تدقيق حقيقي. نفضّل أن نخبركم بالحقيقة المفيدة التي يستطيع جهازان تحقيقها، بدلاً من ادعاء مبهر لا أساس له.

---

## 7. Engineering Rigor & Honesty (9:00–10:30)

**Slide:** "132 TypeScript tests / 81 Python tests / documented limitations"

**EN:**
> Before I show you the demo, I want to establish credibility on process, not just the pitch. This system has 132 passing TypeScript tests and 81 passing Python tests covering the ingest, fusion, and DSP logic. We keep architecture decision records for the choices that matter — like why the Node server, and not the Python reference implementation, owns the live network path. And critically, our own documentation has a section called "Honest Limitations" that we show to every reader, not just this room: it states plainly that this is one-dimensional only, that our detection thresholds are calibration placeholders pending real-hardware validation, and that full empty-room and false-positive testing — fans, curtains, HVAC — hasn't been completed yet. I'm telling you that now, on purpose, because I'd rather you hear it from me than discover it later.

**AR:**
> قبل أن أعرض لكم التجربة الحية، أود أن أرسّخ المصداقية من ناحية المنهجية، وليس فقط من ناحية العرض التقديمي. يحتوي هذا النظام على 132 اختبارًا ناجحًا بلغة TypeScript و81 اختبارًا ناجحًا بلغة Python، تغطي منطق الاستقبال والدمج والمعالجة الرقمية للإشارة. نحتفظ بسجلات قرارات معمارية موثّقة للخيارات المهمة — مثل سبب امتلاك خادم Node، لا التطبيق المرجعي بلغة Python، للمسار التشغيلي الحي. والأهم من ذلك، أن توثيقنا نفسه يحتوي على قسم بعنوان "القيود الصادقة" نعرضه لكل قارئ، وليس فقط لهذه القاعة: وينص بوضوح على أن النظام أحادي البُعد فقط، وأن عتبات الكشف لدينا هي قيم مبدئية مؤقتة بانتظار التحقق على عتاد حقيقي، وأن اختبارات الغرفة الفارغة والإيجابيات الكاذبة — كالمراوح والستائر وأنظمة التكييف — لم تكتمل بعد. أخبركم بهذا الآن، عن قصد، لأنني أفضّل أن تسمعوه مني بدلًا من أن تكتشفوه لاحقًا.

---

## 8. Live Demo (10:30–15:00) — ~4.5 min

**Pre-flight checklist (do this before you walk into the room):**
- [ ] Both ESP32-S3 nodes flashed with current firmware and provisioned to the venue's Wi-Fi (or a hotspot you control) — confirm `PHANTOM_ALLOW_LEGACY_CSI` is *not* needed for your current firmware build.
- [ ] Host laptop on the same network, `npm run dev:dashboard` tested end-to-end at the venue at least once beforehand, not just at home.
- [ ] Login credentials ready — the shipped dev seed is `thaer` / `thaer`; **do not present this as a real credential policy**, mention proactively that this is a development convenience if anyone asks about auth.
- [ ] UDP `:5005` allowed through the host firewall (`netsh advfirewall firewall add rule name="ESP32 CSI" dir=in action=allow protocol=UDP localport=5005`).
- [ ] **Backup plan**: a 60–90 second screen recording of a working session, in case a node drops, Wi-Fi is congested, or the venue network blocks UDP. Have it cued up and ready to play with one click.

**EN — demo narration:**
> Let's make this real. [Switch to dashboard on screen.] I'm starting a live scan now — you're looking at two physical radios in this room, right there [point], streaming real Wi-Fi channel data to this laptop over the network, right now, with zero cameras anywhere in this room.
>
> Watch the radar view. When no one's moving between the nodes, the system shows nothing — no ghost target, no fake presence. That's deliberate: we explicitly removed every fallback in this codebase that used to invent a demo target when the real signal was idle, because a sensor that shows a person who isn't there is worse than a sensor that shows nothing.
>
> Now [walk between the two nodes] — watch the target appear on the line between N1 and N2, and track as I move closer to one node and then the other. You can see the distance readout and the approach/recede trend update live. [Point to the Board DSP panel.] This second panel is computed independently, directly on the firmware — motion, presence, and a breathing-rate estimate — kept deliberately separate from the fused result on the main view, so you're seeing two independent computations agree with each other in real time, not one number dressed up two ways.

**AR — سرد العرض الحي:**
> لنجعل هذا الأمر ملموسًا. [التحويل إلى لوحة التحكم على الشاشة.] سأبدأ الآن مسحًا حيًا — أمامكم جهازان لاسلكيان فعليان في هذه القاعة، هناك تحديدًا [الإشارة إليهما]، يبثّان بيانات قناة واي-فاي حقيقية إلى هذا الحاسوب عبر الشبكة، الآن، دون أي كاميرا في هذه القاعة إطلاقًا.
>
> راقبوا عرض الرادار. عندما لا يتحرك أحد بين العقدتين، لا يُظهر النظام أي شيء — لا هدف وهمي، ولا وجود مزيّف. هذا أمر متعمّد: أزلنا صراحة كل آلية احتياطية في هذا الكود كانت سابقًا تخترع هدفًا تجريبيًا عندما تكون الإشارة الحقيقية خاملة، لأن مستشعرًا يُظهر شخصًا غير موجود هو أسوأ من مستشعر لا يُظهر شيئًا.
>
> الآن [المشي بين العقدتين] — راقبوا ظهور الهدف على الخط الواصل بين N1 وN2، وتتبّعوه وأنا أقترب من عقدة ثم من الأخرى. يمكنكم رؤية قراءة المسافة واتجاه الاقتراب أو الابتعاد تتحدّث لحظيًا. [الإشارة إلى لوحة Board DSP.] هذه اللوحة الثانية تُحسب بشكل مستقل، مباشرة على البرمجيات الثابتة — الحركة، الحضور، وتقدير معدل التنفس — ومفصولة عمدًا عن النتيجة المدمجة في العرض الرئيسي، بحيث ترون حسابين مستقلَّين يتوافقان مع بعضهما لحظيًا، لا رقمًا واحدًا مُقدَّمًا بشكلين.

---

## 9. Current Status / Where This Really Stands (15:00–16:15)

**Slide:** Simple traffic-light table — proven vs. pending

**EN:**
> So where does this actually stand? What you just saw is real — real firmware, real UDP protocol, real signal processing, running end-to-end on real hardware. Our test suite is green. What's *not* yet done is a rigorous field calibration campaign: establishing a validated empty-room baseline, running negative controls against fans and HVAC and curtains, and tuning our detection thresholds — which are currently reasonable placeholder values, not validated ones — against that real-world data. That's the honest gap between a working prototype and a deployable sensor, and it's exactly the gap that funding closes fastest.

**AR:**
> إذن أين يقف هذا المشروع فعليًا؟ ما شاهدتموه للتو حقيقي — برمجيات ثابتة حقيقية، بروتوكول UDP حقيقي، معالجة إشارة حقيقية، تعمل من طرف إلى طرف على عتاد حقيقي. مجموعة اختباراتنا ناجحة بالكامل. أما ما لم يُنجز بعد فهو حملة معايرة ميدانية دقيقة: إرساء خط أساس موثّق لغرفة فارغة، وإجراء اختبارات ضبط سلبية مقابل المراوح وأنظمة التكييف والستائر، وضبط عتبات الكشف لدينا — وهي حاليًا قيم مبدئية معقولة، لا قيمًا مُتحقَّقًا منها — استنادًا لتلك البيانات الواقعية. هذه هي الفجوة الصادقة بين نموذج أولي عامل ومستشعر جاهز للنشر، وهي بالضبط الفجوة التي يُغلقها الدعم المالي بأسرع شكل.

---

## 10. Roadmap — What Funding Unlocks (16:15–17:30)

**Slide:** Phase 1 (calibration) → Phase 2 (pilot) → Phase 3 (multi-node mesh)

**EN:**
> With [FUNDING AMOUNT] over [TIMELINE], here's exactly what we'd deliver:
> **Phase one** — a validated real-hardware calibration campaign: empty-room baselines, negative controls, and thresholds backed by measured data instead of placeholders.
> **Phase two** — a pilot deployment at [PILOT SITE], proving the system in a real environment with real walls and real interference sources, not a lab bench.
> **Phase three**, looking further out — extending beyond two nodes toward a multi-node mesh, which is the architecture path toward genuine two-dimensional localization instead of the honest one-dimensional result we have today. I want to be clear that phase three is a research direction, not a promise — but it's the natural next step once the two-node foundation has actually been calibrated and validated, which it has not yet been (the detection threshold is provisional).

**AR:**
> بدعم بقيمة [FUNDING AMOUNT] على مدى [TIMELINE]، إليكم بالضبط ما سنقدّمه:
> **المرحلة الأولى** — حملة معايرة موثّقة على عتاد حقيقي: خطوط أساس لغرفة فارغة، اختبارات ضبط سلبية، وعتبات كشف مبنية على بيانات مقاسة فعليًا بدلًا من قيم افتراضية.
> **المرحلة الثانية** — نشر تجريبي في [PILOT SITE]، لإثبات عمل النظام في بيئة حقيقية بجدران حقيقية ومصادر تشويش حقيقية، لا على طاولة مختبر.
> **المرحلة الثالثة**، بمنظور أبعد — التوسع إلى ما هو أبعد من عقدتين نحو شبكة متعددة العقد، وهو المسار المعماري نحو تموضع ثنائي الأبعاد حقيقي بدلًا من النتيجة الصادقة أحادية البُعد التي نمتلكها اليوم. أود أن أوضح أن المرحلة الثالثة هي توجه بحثي، وليست وعدًا — لكنها الخطوة التالية الطبيعية بمجرد معايرة الأساس ثنائي العقدة والتحقق منه فعليًا، وهو ما لم يتم بعد (عتبة الكشف الحالية مؤقتة).

---

## 11. The Ask (17:30–18:45)

**Slide:** The specific ask, in numbers

**EN:**
> Concretely, here's what we're asking JODDB for: [FUNDING AMOUNT], allocated to [hardware / calibration equipment / engineering time / pilot site access — pick what's real]. In return, within [TIMELINE], you get a calibrated, field-validated presence sensor built on hardware costing a few dollars per node, with no camera and no wearable dependency, and — because it's built the way we just showed you, with tests and honest documentation — something you can defend technically to your own stakeholders, not just a demo that worked once in a lab.

**AR:**
> بشكل محدد، إليكم ما نطلبه من [JODDB FULL NAME]: [FUNDING AMOUNT]، مخصصة لـ [العتاد / معدات المعايرة / وقت هندسي / الوصول لموقع تجريبي — اختر ما ينطبق فعليًا]. في المقابل، وخلال [TIMELINE]، ستحصلون على مستشعر حضور مُعايَر وموثَّق ميدانيًا، مبني على عتاد لا تتجاوز تكلفته بضعة دولارات لكل عقدة، دون كاميرا ودون اعتماد على جهاز يُلبَس — ولأنه مبني بالطريقة التي عرضناها للتو، بالاختبارات والتوثيق الصادق، فهو أمر يمكنكم الدفاع عنه تقنيًا أمام أصحاب المصلحة لديكم، لا مجرد عرض توضيحي نجح مرة واحدة في المختبر.

---

## 12. Closing & Thanks (18:45–19:30)

**EN:**
> To close: we set out to build a sensor that tells the truth — about what it can see, and just as importantly, about what it can't. What you saw today is a real, tested, working two-node system, with a clear and specific path to a calibrated field-ready product. We'd be glad to leave the hardware here for closer inspection, walk through the code and test suite with your engineering team, or answer anything in more depth. Thank you — [YOUR NAME], on behalf of [TEAM/SUPERVISOR'S LAB].

**AR:**
> ختامًا: سعينا لبناء مستشعر يقول الحقيقة — حول ما يستطيع رؤيته، وبنفس القدر من الأهمية، حول ما لا يستطيعه. ما شاهدتموه اليوم هو نظام حقيقي، مُختبَر، وعامل بجهازين، مع مسار واضح ومحدد نحو منتج مُعايَر وجاهز للميدان. يسعدنا أن نترك العتاد هنا لمزيد من الفحص، أو أن نستعرض الكود ومجموعة الاختبارات مع فريقكم الهندسي، أو الإجابة عن أي استفسار بتفصيل أكبر. شكرًا لكم — [YOUR NAME]، نيابة عن [TEAM/SUPERVISOR'S LAB].

---

## Appendix A — Anticipated Q&A (prepare these cold)

These are the questions a telecom head engineer and a regulator are most likely to ask. Answers are grounded in what the repo actually documents — verify each one still matches your current build before presenting.

**Q: Does this interfere with existing Wi-Fi networks or telecom infrastructure?**
> No new emissions are introduced — the nodes are standard 802.11 clients operating within normal Wi-Fi power and channel limits. Sensing is derived passively from CSI already computed during ordinary traffic. [If your ESP32-S3 modules carry FCC/CE type-approval out of the box, say so and offer to provide the module's certification documentation. If you haven't checked Jordan's TRC/local certification requirements for this specific hardware, say that explicitly rather than guessing — "we haven't yet confirmed local type-approval for this module; that's part of what we'd want your guidance on."]

**Q: What about privacy and data handling?**
> No images or video are ever captured — the raw data is signal amplitude/phase per subcarrier, not optically identifiable. The dashboard has operator authentication and an audit log. [State plainly what you do and don't currently do with data retention/storage — don't improvise this live if you're not certain.]

**Q: How accurate is it, really?**
> Point to the Honest Limitations section directly: one-dimensional only (position along the N1–N2 line, not a full 2D/3D map), and detection thresholds are calibration placeholders, not yet validated against real-hardware empty-room and negative-control testing. That validation is exactly what the funding ask covers.

**Q: How does this compare to a camera or mmWave radar system?**
> Cameras and LIDAR give far richer spatial detail but capture biometric/optical data and cost far more per sensor. mmWave radar can give better native ranging but is a specialized, more expensive RF component. Phantom Scan trades some precision (1-D vs. full 2D/3D) for near-zero marginal hardware cost, no optical capture, and reuse of ubiquitous, already-certified Wi-Fi silicon.

**Q: What happens if one node fails or loses connection?**
> The system is explicitly designed for graceful degradation: it stays up on a single node, per-node processing keeps running, and it withholds the fused two-node result rather than fabricating one — it will not silently invent a position when it can't compute one honestly.

**Q: What's the actual per-unit cost at scale?**
> [State your real, defensible number here — see the cost note at the top of this document. Don't quote a number you can't back with a bill of materials if asked to itemize it on the spot.]

**Q: Is any of this AI/ML, and if so, how do you validate it?**
> The core detection and fusion pipeline is deterministic signal processing — no machine learning — which is auditable and reproducible math. There's an optional, isolated AI inference sidecar for future enhancement, clearly marked non-authoritative, and the system is required to keep working correctly with it fully absent.

**Q: What's the realistic timeline to a deployable product?**
> [Answer this with your real roadmap — Section 10 above gives you the three-phase structure. Don't commit to a date you haven't validated with your supervisor/team.]

---

## Appendix B — Slide List (for your deck)

1. Title
2. The problem (camera / wearable / blind-spot triangle)
3. The idea in one sentence
4. Relevance to JODDB / spectrum-neutral framing
5. Architecture diagram (5 layers)
6. Phantom Balance Fusion diagram (N1—●—N2)
7. Test counts + "Honest Limitations" screenshot from the README
8. **[Live demo — no slide, switch to screen]**
9. Status: proven vs. pending (traffic-light table)
10. Roadmap (3 phases)
11. The ask (numbers)
12. Thank you / contact

---

## Appendix C — Delivery tips

- **Rehearse the demo out loud, with the real hardware, at least twice before the real presentation** — CSI-based sensing is sensitive to RF environment, and venue Wi-Fi congestion or a busy room can behave differently than your test bench at home.
- If the demo glitches live, don't apologize repeatedly — say once, calmly, "this is exactly the kind of real-world variability our calibration phase is designed to characterize," and move to the backup recording.
- The "Honest Limitations" section is your strongest credibility asset in a room with a skeptical engineer — lead with it rather than waiting to be caught out. Regulators and senior engineers trust builders who volunteer their own weaknesses more than builders who don't mention any.
- Keep the Arabic and English scripts as two rehearsed options, not something you translate live — code-switching mid-sentence under pressure is where scripts fall apart.
