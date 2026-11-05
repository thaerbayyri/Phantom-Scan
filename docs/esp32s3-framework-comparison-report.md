# تقرير: مقارنة Framework الـ ESP32-S3 بين Phantom Scan و RuView، وتحديثات الفرع الأخيرة

**التاريخ:** 2026-10-20
**الفرع المرجعي:** `feat/two-node-radar-live-detection`
**المصادر:** `git log` المحلي، كود [firmware/esp32-csi-node](../firmware/esp32-csi-node) في Phantom Scan، نسخة RuView المحلية في `C:\Users\thaer\.claude\plugins\marketplaces\ruview\firmware\esp32-csi-node`، وذاكرة المشروع (`ruview-port-4node-status`, `fps-fix-and-embed-drift-pending`).

---

## 1. ملخص التحديثات الأخيرة على Phantom Scan

آخر 10 commits على الفرع نفّذت خطة "RuView-informed 4-node overhaul" بالكامل (10 مراحل، commits من `f121ce3` إلى `a927dac`، ثم `744ce43` كـ merge):

- إصلاحات أساسية في framework الالتقاط، وتهيئة جيومتريا الغرفة عبر [config/room.json](../config/room.json) بدل القيم الثابتة
- تصحيح فلتر Kalman، والتقاط subcarriers من نوع LLTF بترتيب I/Q الصحيح (imaginary-first، وهو ترتيب خاص بـ ESP-IDF)
- ميزة **خاصة بـ Phantom وغير موجودة في RuView**: فلترة حزم CSI حسب MAC جهاز الإرسال قبل بوابة معدل الالتقاط (rate-gate)، في [firmware/esp32-csi-node/main/csi_collector.c](../firmware/esp32-csi-node/main/csi_collector.c)
- baseline تكيّفي لكل عقدة (per-node adaptive baseline)، أداة تسجيل dataset موسومة، مُصنّف نشاط لكل غرفة، وشبكة CNN لعدّ الأشخاص (0 / 1 / 2+)
- **كل مخرجات الذكاء الاصطناعي استشارية (advisory) فقط** — لم يتم التحقق من دقتها بعد

عمل لا يزال غير مكتمل (بحسب ذاكرة المشروع):
- إصلاح توقيت ping في `csi_ping_pure.h` (تقليل timeout إلى 20ms، interval إلى 30ms) تم بناؤه وفلشه على العقد الأربع، لكن لم يُعاد قياس fps بكل العقد الأربع تعمل معًا في نفس الوقت
- مقياس drift الخاص بـ `csi-embed-v2` موصول في الواجهة الجانبية للذكاء الاصطناعي، لكن بلا تحقق فعلي من قدرته على الفصل بين غرفة فاضية وغرفة مشغولة
- عتبات `PHANTOM_ROOM_TIER_STILL/MOVING/ACTIVE` مؤقتة (provisional) ولم تُضبط بعد اختبار إشباع لا يقل عن 5 دقائق في غرفة فاضية
- `room.json` لا يزال يحمل زوايا افتراضية 4×6 متر وليس المواقع الحقيقية المقاسة

---

## 2. مقارنة framework الـ ESP32-S3 بين Phantom Scan و RuView

كلا المشروعين يستخدمان **ESP-IDF النقي (ليس Arduino framework)** بلغة C. فعليًا، مجلد [firmware/esp32-csi-node](../firmware/esp32-csi-node) في Phantom Scan هو منفذ (port) حرفي من بنية RuView نفسها — نفس اسم المجلد تمامًا، ونفس تعليق `ADR-018` الموروث في أعلى `CMakeLists.txt`.

| الجانب | Phantom Scan | RuView |
|---|---|---|
| إصدار ESP-IDF | مثبّت على 5.5.2 (`dependencies.lock`) | معلّق على v5.2+ في `CMakeLists.txt`، تعليقات الكود تشير لـ "stock IDF v5.4 defaults" |
| ضبط LWIP / WiFi لأجل CSI | **لا يوجد أي تعديل** في `sdkconfig.defaults` | `CONFIG_LWIP_UDP_RECVMBOX_SIZE=32`, `CONFIG_LWIP_TCPIP_RECVMBOX_SIZE=64`, `CONFIG_ESP_WIFI_DYNAMIC_TX_BUFFER_NUM=64` — إصلاح موثّق بالتفصيل في تعليقات الكود لمشكلة `sendto` تفشل بـ `ENOMEM` وتُسقط نحو 90% من فريمات CSI تحت وضع promiscuous |
| حجم المكدّس (stack) | القيم الافتراضية لـ ESP-IDF | `CONFIG_ESP_MAIN_TASK_STACK_SIZE=8192` و `CONFIG_FREERTOS_TIMER_TASK_STACK_DEPTH=8192` — الأخير يمنع bootloop فعلي كان يحدث بسبب stack overflow في مهمة `Tmr Svc` |
| تحسين الحجم / الموضع في الذاكرة | غير مفعّل | `CONFIG_COMPILER_OPTIMIZATION_SIZE=y` و `CONFIG_ESP_WIFI_EXTRA_IRAM_OPT=y` (دفاع إضافي ضد سباق SPI cache) |
| اختبار بلا هاردوير | وحدات "pure" مستقلة (`csi_filter_pure.c`, `csi_ping_pure.h`, `edge_dsp_pure.c`) تُختبر محليًا بـ gcc على جهاز المطوّر | طبقة HAL كاملة `rv_radio_ops.h` (تطبيق حقيقي esp32 + تطبيق mock) مع `mock_csi.c`، تسمح بتشغيل **الـ firmware الكامل** تحت QEMU داخل CI (`firmware-qemu.yml`) |
| إصدار الـ firmware | لا يوجد وسم إصدار | ملف `version.txt` يُقرأ في `CMakeLists.txt` ويُضمَّن في `esp_app_desc`، فيظهر الإصدار فعليًا عند الفحص بعد الفلاشة |
| الشاشة / اللمس | معطّلة عمدًا لمرحلة "headless milestone-1" (`CONFIG_DISPLAY_ENABLE=n`، و `idf_component.yml` فارغ)، لكن ملفات `display_hal/task/ui.c` و `lv_conf.h` لا تزال موجودة في الشجرة كأكواد غير مستخدمة | LVGL + `esp_lcd_touch_cst816s` كمكوّنات managed فعّالة ومُستخدَمة |
| هاردوير إضافي مدعوم | ESP32-S3 فقط | يدعم أيضًا ESP32-C6 كمرافق (`c6_twt.c` توفير طاقة TWT، `c6_softap_he.c` 802.11ax HE، `c6_sync_espnow.c` مزامنة وقت)، إضافة لاستشعار mmWave (`mmwave_sensor.c`)، شبكة mesh (`rv_mesh.c`)، ومنسّق swarm (`swarm_bridge.c`) |

**الخلاصة الجوهرية:** Phantom نقل الكود الذي *يتعامل مع أعراض* مشكلة إسقاط فريمات CSI (منطق إعادة المحاولة بعد `sendto ENOMEM` في [stream_sender.c](../firmware/esp32-csi-node/main/stream_sender.c)) لكنه **لم ينقل سبب الإصلاح الحقيقي** الموجود في ملف `sdkconfig.defaults` لدى RuView. هذا يتطابق تقريبًا تمامًا مع نوع العطل الذي عالجه فريق Phantom جزئيًا فقط عبر ضبط توقيت `ping` (انظر الذاكرة `fps-fix-and-embed-drift-pending`)، وهي معالجة للأعراض لا للسبب الجذري.

---

## 3. التحسينات المقترحة لمشروع Phantom (مرتّبة بالأولوية)

1. **أعلى قيمة وأقل جهد:** نقل ضبط `sdkconfig.defaults` من RuView مباشرة:
   ```
   CONFIG_LWIP_UDP_RECVMBOX_SIZE=32
   CONFIG_LWIP_TCPIP_RECVMBOX_SIZE=64
   CONFIG_ESP_WIFI_DYNAMIC_TX_BUFFER_NUM=64
   CONFIG_ESP_MAIN_TASK_STACK_SIZE=8192
   CONFIG_FREERTOS_TIMER_TASK_STACK_DEPTH=8192
   CONFIG_ESP_WIFI_EXTRA_IRAM_OPT=y
   CONFIG_COMPILER_OPTIMIZATION_SIZE=y
   ```
   ثم إعادة قياس fps على الأربع عُقد معًا. هذا يعالج جذر مشكلة إسقاط الفريمات بدل الاعتماد فقط على توقيت ping.

2. **تنظيف الكود الميت:** إما حذف `display_hal/task/ui.c` و `lv_conf.h` بما أن القرار الحالي هو "headless"، أو تفعيلها رسميًا عبر flag موثّق في الكود والوثائق. تركها معلّقة بلا استخدام يخالف مبدأ YAGNI المعتمَد في معايير الترميز الخاصة بالمشروع.

3. **اعتماد نمط HAL لعمليات الراديو** (مثل `rv_radio_ops.h` + mock من RuView) لإضافة اختبار QEMU لكامل الـ firmware، لأن اختبارات "_pure" الحالية تغطي فقط رياضيات الفلتر/DSP ولا تكشف أخطاء التكامل (مثل `ENOMEM` أو stack overflow) قبل الفلاشة الفعلية على الهاردوير.

4. **إضافة وسم إصدار للـ firmware** (`version.txt` → `PROJECT_VER`) لمعرفة أي نسخة بناء مُثبَّتة على أي عقدة (COM5/6/8/9) بدقة، خصوصًا مع إعادة الفلاشة المتكررة لعقد منفصلة.

5. **عدم استنساخ** دعم C6 / mesh / swarm / mmWave من RuView في الوقت الحالي — هذه الميزات موجهة لهاردوير وأهداف مختلفة (طاقة محمولة، شبكات متعددة الأجهزة) وغير مطلوبة للنشر الحالي المكوَّن من 4 عُقد ESP32-S3 فقط. إضافتها الآن تُعد هندسة استباقية غير مطلوبة (YAGNI).

6. **إغلاق العمل غير المكتمل أولًا** قبل البناء على هذه المقارنة عمليًا:
   - إعادة قياس fps بعد آخر تعديل في توقيت ping، وبكل العقد الأربع تعمل معًا
   - تدريب والتحقق من مقياس drift الخاص بـ `csi-embed-v2` (فصل فعلي بين غرفة فاضية/مشغولة)
   - تحديث `room.json` بالمواقع الحقيقية المقاسة بدل الزوايا الافتراضية 4×6 متر
   - ضبط عتبات `PHANTOM_ROOM_TIER_STILL/MOVING/ACTIVE` بعد اختبار إشباع فعلي لا يقل عن 5 دقائق

---

## 4. حالة التنفيذ (2026-10-20)

| # | التحسين | الحالة |
|---|---|---|
| 1 | ضبط `sdkconfig.defaults` (LWIP/WiFi/stack/compiler) | **منفّذ ومُتحقَّق منه** — تمت إضافة القيم إلى `sdkconfig.defaults` وإعادة توليد `sdkconfig` من الصفر، وبُني الـ firmware بالكامل بنجاح (`idf.py build`, exit code 0) على ESP-IDF 5.5.2 |
| 2 | تنظيف كود الشاشة الميت | **لا حاجة لتغيير** — تبيّن أن `display_hal.c`/`display_ui.c` محميان فعليًا بشرط `CONFIG_DISPLAY_ENABLE` في `main/CMakeLists.txt`، و`display_task.c` نفسه محاط بـ `#if CONFIG_DISPLAY_ENABLE` داخليًا (ADR-045) — هذا هو نمط "التفعيل بعلم واضح" الذي أوصى به التقرير أصلًا، وليس كودًا معلّقًا بلا تغطية |
| 3 | طبقة HAL + اختبار QEMU | **جزئي** — أُضيف خيار `CONFIG_CSI_MOCK_ENABLED` في `main/Kconfig.projbuild` ومولّد CSI وهمي معزول داخل `csi_collector.c` (محاط بـ `#if`، المسار الحقيقي للهاردوير لم يتغيّر حرفيًا). **لم يكتمل**: تثبيت `qemu-xtensa` فشل على هذا الجهاز (access violation 0xC0000005 عند تشغيل الملف التنفيذي المُنزَّل — مشكلة بيئة Windows محلية، ليست في الكود)، فلم يتسنَّ تشغيل اختبار إقلاع QEMU فعليًا. سكربت التشغيل وworkflow الخاص بـ CI (على غرار `firmware-qemu.yml` في RuView) لم يُكتبا بعد — يُنصح بتشغيلهما على Linux runner (GitHub Actions أو WSL) حيث يُثبَّت `qemu-system-xtensa` بسهولة عبر apt |
| 4 | وسم إصدار الـ firmware | **منفّذ ومُتحقَّق منه** — `version.txt` (0.1.0) + تعديل `CMakeLists.txt` الجذري؛ ظهر فعليًا في سجل البناء: `App "esp32-csi-node" version: 0.1.0` |
| 5 | عدم استنساخ C6/mesh/swarm/mmWave | **تم تطبيقها كما أوصي بها — أي لم يُضاف شيء عمدًا** |
| 6 | إغلاق العمل غير المكتمل (قياس fps، تحقق drift، مواقع room.json الحقيقية، عتبات التصنيف) | **يتطلب هاردوير فعلي ولا يمكن تنفيذه من الكود وحده** — يبقى على عاتق المستخدم تنفيذه على الأجساد الأربعة الفعلية |

---

## 5. البحث عن مجموعات بيانات لتدريب نماذج النشاط/العدّ (CNN) الخاصة بـ Phantom

كل ما يلي عبارة عن مجموعات بيانات CSI عامة يمكن استخدامها لتهيئة أولية (pretraining) أو تدريب نقلي (transfer learning) قبل الدقة النهائية على بيانات Phantom الحقيقية المسجَّلة عبر `docs/DATASET_PROTOCOL.md`، لأن لا بديل عن بيانات حقيقية من نفس الهاردوير والغرفة لضبط عتبات حساسة بيئيًا:

- **[WiCount (Hugging Face)](https://huggingface.co/datasets/RS2002/WiCount)** — الأقرب مباشرة لمهمة "عدّ الأشخاص" في Phantom: CSI+RSSI من أجهزة **ESP32-S3** لعدّ 0-3 أشخاص في غرفة اجتماعات. الكود المرتبط: `github.com/RS2002/CSI-BERT2`.
- **[WiFall (Hugging Face)](https://huggingface.co/datasets/RS2002/WiFall)** — CSI/RSSI متزامن من **ESP32-S3** لاكتشاف السقوط والتعرف على الحركة (سقوط/قفز/جلوس/وقوف/مشي) لـ10 أفراد — نفس عائلة هاردوير Phantom تمامًا.
- **Gupta et al. ([IEEE DataPort](https://ieee-dataport.org/), DOI 10.21227/e6c6-aa21)** — أكبر عدد مشاركين (80+) بستة أنشطة عبر ESP32-CSI Toolkit، بإعدادات لمستخدم واحد/اثنين/ثلاثة — مفيد لتوسيع تنوّع بيانات التدريب.
- **Zenodo (فبراير 2026) — "Less is More: The Dilution Effect in Multi-Link Wireless Sensing"** — شبكة mesh من 9 عقد **ESP32-C3**، أكثر من 300 ساعة تسجيل، تصنيفات presence/activity/occupancy count — أقرب مثال لبنية Phantom متعددة العقد (4 عقد)، لكنه هاردوير C3 لا S3 ومقاس الملف ضخم (~45.7 GB).
- **EHUNAM (figshare, DOI 10.6084/m9.figshare.28541225.v1)** — عدّ أشخاص + تصنيف نشاط + machine sensing عبر 23 يوم تسجيل في 8 بيئات مختلفة، ترخيص CC BY 4.0.
- **CSI Dataset for Wireless Human Sensing on 80MHz (IEEE DataPort, DOI 10.21227/xbhv-f125)** — تعرّف على النشاط + هوية الشخص + عدّ الأشخاص، حتى 7 أنشطة و10 أفراد عبر 7 بيئات (غرفة نوم، صالة، مطبخ، مكاتب، غرفة اجتماعات).
- **إطار Espressif الرسمي: [esp-radar](https://components.espressif.com/components/espressif/esp-radar) و [esp_wifi_sensing](https://components.espressif.com/components/espressif/esp_wifi_sensing)** — ليست مجموعة بيانات جاهزة، بل خوارزميات حضور/حركة رسمية من Espressif لـ ESP32 مع مثال `console_test` لتسجيل بيانات مُصنَّفة بنفسك؛ ملاحظة توثيقية من Espressif نفسها: خوارزمية الحضور الحالية "ليست مثالية" وتحتاج توليفًا موضعيًا — نفس الدرس المستفاد من RuView.

**توصية عملية:** استخدام WiCount/WiFall كأساس Pretraining لأنهما على ESP32-S3 (نفس عتاد Phantom) ويغطيان مهمتين (العدّ + النشاط) موجودتين بالفعل في خطة Phantom، ثم Fine-tuning على تسجيلات Phantom الحقيقية القادمة وفق `docs/DATASET_PROTOCOL.md` — نقل تعلّم عبر هاردوير مختلف (802.11ac التجاري) أقل فائدة بسبب اختلاف خصائص الإشارة.

---

*مراجع ذات صلة في ذاكرة المشروع: `ruview-port-4node-status`, `fps-fix-and-embed-drift-pending`, `running-4-node-fused-room`, `esp-idf-on-e-drive`.*
