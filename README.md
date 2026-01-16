# JavidNet - جاویدنت

<div align="center">

```
     ██╗ █████╗ ██╗   ██╗██╗██████╗ ███╗   ██╗███████╗████████╗
     ██║██╔══██╗██║   ██║██║██╔══██╗████╗  ██║██╔════╝╚══██╔══╝
     ██║███████║██║   ██║██║██║  ██║██╔██╗ ██║█████╗     ██║   
██   ██║██╔══██║╚██╗ ██╔╝██║██║  ██║██║╚██╗██║██╔══╝     ██║   
╚█████╔╝██║  ██║ ╚████╔╝ ██║██████╔╝██║ ╚████║███████╗   ██║   
 ╚════╝ ╚═╝  ╚═╝  ╚═══╝  ╚═╝╚═════╝ ╚═╝  ╚═══╝╚══════╝   ╚═╝   
```

### The Eternal Network | شبکه جاوید

**"اینترنت نمی‌میرد" — The Internet Never Dies**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)
[![Status](https://img.shields.io/badge/Status-Proposal-blue.svg)]()

</div>

---

## 🌐 Language | زبان

- [English](#english)
- [فارسی (Persian)](#فارسی-persian)

---

# English

## 📖 Table of Contents

- [Overview](#overview)
- [The Problem](#the-problem)
- [Our Vision](#our-vision)
- [Technical Architecture](#technical-architecture)
- [Implementation Phases](#implementation-phases)
- [Challenges & Mitigations](#challenges--mitigations)
- [Bandwidth Analysis](#bandwidth-analysis)
- [How to Contribute](#how-to-contribute)
- [Disclaimer](#disclaimer)

---

## Overview

**JavidNet** (جاویدنت - "Eternal Network") is a proposal for a people-managed, decentralized internet infrastructure designed to maintain connectivity during complete internet shutdowns. 

This project outlines a technical framework for routing internal network traffic through satellite exit nodes, enabling citizens to access the global internet even when traditional ISP connections are severed.

> **Note:** This is a conceptual proposal and technical discussion document. Implementation requires careful consideration of local laws, safety implications, and operational security.

---

## The Problem

During times of civil unrest, governments may implement complete internet blackouts, cutting off millions of people from:

- 📰 **News and information** — Access to independent journalism and global news
- 👨‍👩‍👧‍👦 **Family communication** — Contact with loved ones abroad
- 🏥 **Emergency services** — Coordination during crises
- 💼 **Economic activity** — Business operations, banking, commerce
- 🗣️ **Free expression** — The fundamental right to communicate

**Critical observation:** During these shutdowns, *internal networks often remain operational*. Domestic services, banking apps, and local websites continue to function. This creates an opportunity.

---

## Our Vision

### Core Principles

| Principle | Description |
|-----------|-------------|
| **Decentralized** | No single point of control or failure |
| **People-Managed** | Operated by citizens, for citizens |
| **Resilient** | Designed to survive targeted attacks |
| **Accessible** | Simple enough for non-technical users |
| **Secure** | Privacy-preserving by design |

### The Concept

```
┌─────────────────────────────────────────────────────────────┐
│                     GLOBAL INTERNET                          │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ Satellite Link
                              │ (Bypasses ISP control)
                    ┌─────────┴─────────┐
                    │  STARLINK EXIT    │
                    │      NODES        │
                    │  (Hidden within   │
                    │   the country)    │
                    └─────────┬─────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              INTERNAL NETWORK (Still operational)            │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                  │
│  │ Bridge  │◄──►│ Bridge  │◄──►│ Bridge  │  Snowflake-style │
│  │ Server  │    │ Server  │    │ Server  │  relay network   │
│  └────┬────┘    └────┬────┘    └────┬────┘                  │
│       │              │              │                        │
│       └──────────────┼──────────────┘                        │
│                      ▼                                       │
│              ┌───────────────┐                               │
│              │    USERS      │                               │
│              │  (Millions)   │                               │
│              └───────────────┘                               │
└─────────────────────────────────────────────────────────────┘
```

**The key insight:** Use satellite internet terminals as "exit nodes" that bridge the functioning internal network to the global internet.

---

## Technical Architecture

### System Components

#### 1. Satellite Exit Nodes
Hidden Starlink (or similar satellite internet) terminals that provide the physical bridge to the global internet.

```
┌─────────────────────────────────────────────────────────┐
│                STARLINK EXIT NODE                        │
│  ┌──────────┐   ┌──────────┐   ┌──────────────────┐    │
│  │ Satellite│   │  Router  │   │  Bridge Server   │    │
│  │   Dish   │──►│    PC    │──►│  (Tor + Custom)  │    │
│  └──────────┘   └──────────┘   └────────┬─────────┘    │
│        ▲                                 │              │
│        │ To Space                        ▼              │
│                                  Internal Network       │
└─────────────────────────────────────────────────────────┘
```

#### 2. Bridge Network
A Snowflake-inspired relay system operating over the internal network:
- **Bridge Servers** — Connect to exit nodes and distribute traffic
- **Relay Nodes** — Volunteer-run nodes that forward encrypted traffic
- **Client Software** — User-facing application for seamless access

#### 3. Protocol Stack

| Layer | Function | Technology |
|-------|----------|------------|
| 5 | Application | HTTP/HTTPS, Signal, Telegram |
| 4 | Encryption | TLS 1.3 + E2E encryption |
| 3 | Obfuscation | Traffic shaping, domain fronting |
| 2 | Relay | Modified Snowflake/WebRTC |
| 1 | Transport | Internal network TCP/UDP |
| 0 | Exit | Starlink → Global Internet |

### Architecture Diagrams

Detailed technical diagrams are available in the `/diagrams` folder:

| Diagram | Description |
|---------|-------------|
| `iran-starlink-architecture.drawio` | Complete system overview |
| `iran-starlink-dataflow.drawio` | Request/response flow |
| `iran-starlink-components.drawio` | Hardware & software components |
| `iran-starlink-protocol-stack.drawio` | Protocol layers |
| `iran-starlink-challenges.drawio` | Challenges and solutions |
| `iran-starlink-bandwidth.drawio` | Bandwidth estimation |

> Open these files with [draw.io](https://app.diagrams.net/) or any compatible editor.

---

## Implementation Phases

### Phase 1: Foundation 🔬
*Research and Development*

- [ ] Validate satellite internet bypass techniques
- [ ] Develop bridge server software prototype
- [ ] Design client application architecture
- [ ] Establish secure communication channels for coordination
- [ ] Identify potential hardware suppliers and logistics

### Phase 2: Infrastructure 🛠️
*Building the Network*

- [ ] Acquire and position satellite terminals
- [ ] Deploy initial bridge servers
- [ ] Establish encrypted inter-node communication
- [ ] Implement DHT-based bridge discovery
- [ ] Beta test with limited user group

### Phase 3: Scaling 📈
*Expanding Access*

- [ ] Recruit volunteer relay node operators
- [ ] Distribute client software through secure channels
- [ ] Implement caching and compression systems
- [ ] Establish redundancy and failover procedures
- [ ] Monitor and optimize network performance

### Phase 4: Resilience 🛡️
*Hardening the Network*

- [ ] Implement advanced traffic obfuscation
- [ ] Deploy countermeasures against detection
- [ ] Establish backup exit node locations
- [ ] Create emergency protocols
- [ ] Document operational security procedures

---

## Challenges & Mitigations

| Challenge | Risk Level | Mitigation Strategy |
|-----------|------------|---------------------|
| **Satellite dish detection** | 🔴 High | Hidden locations, camouflage, distributed placement |
| **Bandwidth limitations** | 🟡 Medium | Aggressive caching, compression, text-priority queuing |
| **Bridge discovery** | 🟡 Medium | DHT protocol, QR codes, Bluetooth bootstrap |
| **Traffic analysis** | 🟡 Medium | Traffic shaping, mimicking allowed services |
| **Single point of failure** | 🔴 High | Multiple exit nodes, automatic failover |
| **Hardware logistics** | 🔴 High | Pre-positioning, trusted supply chains |
| **Operational security** | 🔴 High | Compartmentalization, encrypted communications |

---

## Bandwidth Analysis

### Assumptions
- 5 Starlink terminals (100 Mbps down / 20 Mbps up each)
- Total capacity: ~500 Mbps download, ~100 Mbps upload

### Capacity Estimates

| Usage Type | Bandwidth/User | Concurrent Users |
|------------|----------------|------------------|
| Text-only (messaging, news) | ~50 Kbps | 2,000 - 10,000 |
| Mixed (light browsing) | ~200 Kbps | 500 - 2,500 |
| Heavy (video, large files) | ~500 Kbps | 200 - 1,000 |

### Realistic Use Cases

✅ **Viable:**
- Text messaging (Signal, Telegram, WhatsApp)
- News reading and web browsing
- Email communication
- Coordination and organization
- Low-resolution image sharing

⚠️ **Limited:**
- Voice calls (compressed)
- Social media (text-focused)
- Document sharing
- Video streaming
- Video calls
- Large file downloads
- Software updates

---

## How to Contribute

We welcome contributions from:

- **Network Engineers** — Protocol design, optimization
- **Security Researchers** — Threat modeling, penetration testing
- **Software Developers** — Client/server application development
- **UX Designers** — Making the system accessible to all users
- **Technical Writers** — Documentation in multiple languages
- **Translators** — Expanding reach to more communities

### Ways to Help

1. **Review the architecture** — Identify flaws, suggest improvements
2. **Contribute code** — See open issues for current needs
3. **Test and report** — Help identify bugs and vulnerabilities
4. **Spread awareness** — Share with those who might benefit
5. **Donate resources** — Hardware, hosting, development time

### Code of Conduct

- This project is for humanitarian purposes only
- We do not support or encourage any illegal activity
- Safety of users and operators is the top priority
- All contributions must maintain user privacy

---

## Disclaimer

⚠️ **Important Legal Notice**

This repository contains a **technical proposal and discussion document**. The information provided is for educational and research purposes.

- Implementation may be illegal in certain jurisdictions
- Users and operators assume all risks
- The authors provide no warranty and accept no liability
- Always consult local laws before taking any action
- Prioritize personal safety above all else

This project is motivated by the fundamental human right to access information and communicate freely, as recognized by Article 19 of the Universal Declaration of Human Rights.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**"در تاریکی، یک چراغ کافیست"**

*"In darkness, one light is enough"*

</div>

---
---
---

# فارسی (Persian)

<div dir="rtl">

## 📖 فهرست مطالب

- [معرفی](#معرفی)
- [مشکل](#مشکل)
- [چشم‌انداز ما](#چشم‌انداز-ما)
- [معماری فنی](#معماری-فنی)
- [مراحل اجرا](#مراحل-اجرا)
- [چالش‌ها و راه‌حل‌ها](#چالش‌ها-و-راه‌حل‌ها)
- [تحلیل پهنای باند](#تحلیل-پهنای-باند)
- [چگونه مشارکت کنیم](#چگونه-مشارکت-کنیم)
- [سلب مسئولیت](#سلب-مسئولیت)

---

## معرفی

**جاویدنت** (JavidNet) یک پیشنهاد برای زیرساخت اینترنت غیرمتمرکز و مردم‌محور است که برای حفظ اتصال در زمان قطعی کامل اینترنت طراحی شده است.

این پروژه یک چارچوب فنی برای مسیریابی ترافیک شبکه داخلی از طریق گره‌های خروجی ماهواره‌ای ارائه می‌دهد که به شهروندان امکان دسترسی به اینترنت جهانی را حتی در زمان قطع اتصالات ISP سنتی می‌دهد.

> **توجه:** این یک پیشنهاد مفهومی و سند بحث فنی است. اجرای آن نیاز به بررسی دقیق قوانین محلی، پیامدهای امنیتی و امنیت عملیاتی دارد.

---

## مشکل

در زمان ناآرامی‌های مدنی، دولت‌ها ممکن است قطعی کامل اینترنت را اعمال کنند و میلیون‌ها نفر را از موارد زیر محروم کنند:

- 📰 **اخبار و اطلاعات** — دسترسی به روزنامه‌نگاری مستقل و اخبار جهانی
- 👨‍👩‍👧‍👦 **ارتباط خانوادگی** — تماس با عزیزان در خارج از کشور
- 🏥 **خدمات اضطراری** — هماهنگی در بحران‌ها
- 💼 **فعالیت اقتصادی** — عملیات تجاری، بانکداری، تجارت
- 🗣️ **آزادی بیان** — حق اساسی برقراری ارتباط

**مشاهده کلیدی:** در طول این قطعی‌ها، *شبکه‌های داخلی اغلب فعال می‌مانند*. سرویس‌های داخلی، اپلیکیشن‌های بانکی و وب‌سایت‌های محلی همچنان کار می‌کنند. این یک فرصت ایجاد می‌کند.

---

## چشم‌انداز ما

### اصول اساسی

| اصل | توضیح |
|-----|-------|
| **غیرمتمرکز** | بدون نقطه کنترل یا شکست واحد |
| **مردم‌محور** | توسط شهروندان، برای شهروندان |
| **مقاوم** | طراحی شده برای مقاومت در برابر حملات هدفمند |
| **در دسترس** | به اندازه کافی ساده برای کاربران غیرفنی |
| **امن** | حفظ حریم خصوصی در طراحی |

### مفهوم اصلی

```
┌─────────────────────────────────────────────────────────────┐
│                     اینترنت جهانی                            │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ لینک ماهواره‌ای
                              │ (دور زدن کنترل ISP)
                    ┌─────────┴─────────┐
                    │   گره‌های خروجی   │
                    │    استارلینک      │
                    │  (مخفی در داخل    │
                    │      کشور)        │
                    └─────────┬─────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│           شبکه داخلی (همچنان فعال)                          │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                  │
│  │ سرور   │◄──►│ سرور   │◄──►│ سرور   │  شبکه رله        │
│  │  پل    │    │  پل    │    │  پل    │  نوع Snowflake   │
│  └────┬────┘    └────┬────┘    └────┬────┘                  │
│       │              │              │                        │
│       └──────────────┼──────────────┘                        │
│                      ▼                                       │
│              ┌───────────────┐                               │
│              │   کاربران    │                               │
│              │  (میلیون‌ها) │                               │
│              └───────────────┘                               │
└─────────────────────────────────────────────────────────────┘
```

**بینش کلیدی:** استفاده از ترمینال‌های اینترنت ماهواره‌ای به عنوان "گره‌های خروجی" که شبکه داخلی فعال را به اینترنت جهانی متصل می‌کنند.

---

## معماری فنی

### اجزای سیستم

#### ۱. گره‌های خروجی ماهواره‌ای
ترمینال‌های استارلینک (یا اینترنت ماهواره‌ای مشابه) مخفی که پل فیزیکی به اینترنت جهانی را فراهم می‌کنند.

#### ۲. شبکه پل
یک سیستم رله الهام گرفته از Snowflake که روی شبکه داخلی کار می‌کند:
- **سرورهای پل** — اتصال به گره‌های خروجی و توزیع ترافیک
- **گره‌های رله** — گره‌های داوطلبانه که ترافیک رمزگذاری شده را فوروارد می‌کنند
- **نرم‌افزار کلاینت** — برنامه کاربرپسند برای دسترسی بدون دردسر

#### ۳. پشته پروتکل

| لایه | عملکرد | فناوری |
|------|--------|--------|
| ۵ | برنامه | HTTP/HTTPS، سیگنال، تلگرام |
| ۴ | رمزگذاری | TLS 1.3 + رمزگذاری E2E |
| ۳ | مبهم‌سازی | شکل‌دهی ترافیک، domain fronting |
| ۲ | رله | Snowflake/WebRTC اصلاح شده |
| ۱ | انتقال | TCP/UDP شبکه داخلی |
| ۰ | خروج | استارلینک ← اینترنت جهانی |

### نمودارهای معماری

نمودارهای فنی دقیق در پوشه `/diagrams` موجود است:

| نمودار | توضیح |
|--------|-------|
| `iran-starlink-architecture.drawio` | نمای کلی سیستم |
| `iran-starlink-dataflow.drawio` | جریان درخواست/پاسخ |
| `iran-starlink-components.drawio` | اجزای سخت‌افزاری و نرم‌افزاری |
| `iran-starlink-protocol-stack.drawio` | لایه‌های پروتکل |
| `iran-starlink-challenges.drawio` | چالش‌ها و راه‌حل‌ها |
| `iran-starlink-bandwidth.drawio` | تخمین پهنای باند |

> این فایل‌ها را با [draw.io](https://app.diagrams.net/) یا هر ویرایشگر سازگار باز کنید.

---

## مراحل اجرا

### فاز ۱: پایه‌گذاری 🔬
*تحقیق و توسعه*

- [ ] اعتبارسنجی تکنیک‌های دور زدن اینترنت ماهواره‌ای
- [ ] توسعه نمونه اولیه نرم‌افزار سرور پل
- [ ] طراحی معماری برنامه کلاینت
- [ ] ایجاد کانال‌های ارتباطی امن برای هماهنگی
- [ ] شناسایی تامین‌کنندگان سخت‌افزار و لجستیک

### فاز ۲: زیرساخت 🛠️
*ساخت شبکه*

- [ ] تهیه و جایگذاری ترمینال‌های ماهواره‌ای
- [ ] استقرار سرورهای پل اولیه
- [ ] ایجاد ارتباط رمزگذاری شده بین گره‌ها
- [ ] پیاده‌سازی کشف پل مبتنی بر DHT
- [ ] تست بتا با گروه کاربری محدود

### فاز ۳: گسترش 📈
*افزایش دسترسی*

- [ ] جذب اپراتورهای داوطلب گره رله
- [ ] توزیع نرم‌افزار کلاینت از طریق کانال‌های امن
- [ ] پیاده‌سازی سیستم‌های کش و فشرده‌سازی
- [ ] ایجاد رویه‌های افزونگی و failover
- [ ] نظارت و بهینه‌سازی عملکرد شبکه

### فاز ۴: مقاوم‌سازی 🛡️
*تقویت شبکه*

- [ ] پیاده‌سازی مبهم‌سازی پیشرفته ترافیک
- [ ] استقرار اقدامات متقابل در برابر شناسایی
- [ ] ایجاد مکان‌های پشتیبان گره خروجی
- [ ] ایجاد پروتکل‌های اضطراری
- [ ] مستندسازی رویه‌های امنیت عملیاتی

---

## چالش‌ها و راه‌حل‌ها

| چالش | سطح ریسک | استراتژی کاهش |
|------|----------|---------------|
| **شناسایی دیش ماهواره** | 🔴 بالا | مکان‌های مخفی، استتار، توزیع پراکنده |
| **محدودیت پهنای باند** | 🟡 متوسط | کش تهاجمی، فشرده‌سازی، اولویت‌بندی متن |
| **کشف پل** | 🟡 متوسط | پروتکل DHT، کدهای QR، بوت‌استرپ بلوتوث |
| **تحلیل ترافیک** | 🟡 متوسط | شکل‌دهی ترافیک، تقلید سرویس‌های مجاز |
| **نقطه شکست واحد** | 🔴 بالا | چندین گره خروجی، failover خودکار |
| **لجستیک سخت‌افزار** | 🔴 بالا | پیش‌موضع‌گیری، زنجیره تامین قابل اعتماد |
| **امنیت عملیاتی** | 🔴 بالا | تفکیک، ارتباطات رمزگذاری شده |

---

## تحلیل پهنای باند

### فرضیات
- ۵ ترمینال استارلینک (هر کدام ۱۰۰ مگابیت دانلود / ۲۰ مگابیت آپلود)
- ظرفیت کل: ~۵۰۰ مگابیت دانلود، ~۱۰۰ مگابیت آپلود

### تخمین ظرفیت

| نوع استفاده | پهنای باند/کاربر | کاربران همزمان |
|-------------|------------------|----------------|
| فقط متن (پیام‌رسانی، اخبار) | ~۵۰ کیلوبیت | ۲,۰۰۰ - ۱۰,۰۰۰ |
| ترکیبی (مرور سبک) | ~۲۰۰ کیلوبیت | ۵۰۰ - ۲,۵۰۰ |
| سنگین (ویدیو، فایل بزرگ) | ~۵۰۰ کیلوبیت | ۲۰۰ - ۱,۰۰۰ |

### موارد استفاده واقعی

✅ **امکان‌پذیر:**
- پیام‌رسانی متنی (سیگنال، تلگرام، واتساپ)
- خواندن اخبار و مرور وب
- ارتباط ایمیلی
- هماهنگی و سازماندهی
- اشتراک‌گذاری تصاویر با وضوح پایین

⚠️ **محدود:**
- تماس صوتی (فشرده شده)
- شبکه‌های اجتماعی (متن‌محور)
- اشتراک‌گذاری اسناد
- پخش ویدیو
- تماس تصویری
- دانلود فایل‌های بزرگ
- به‌روزرسانی نرم‌افزار

---

## چگونه مشارکت کنیم

ما از مشارکت موارد زیر استقبال می‌کنیم:

- **مهندسان شبکه** — طراحی پروتکل، بهینه‌سازی
- **محققان امنیت** — مدل‌سازی تهدید، تست نفوذ
- **توسعه‌دهندگان نرم‌افزار** — توسعه برنامه کلاینت/سرور
- **طراحان UX** — در دسترس کردن سیستم برای همه کاربران
- **نویسندگان فنی** — مستندسازی به چندین زبان
- **مترجمان** — گسترش دسترسی به جوامع بیشتر

### راه‌های کمک

۱. **بررسی معماری** — شناسایی نقص‌ها، پیشنهاد بهبود
۲. **مشارکت در کد** — مشاهده issues باز برای نیازهای فعلی
۳. **تست و گزارش** — کمک به شناسایی باگ‌ها و آسیب‌پذیری‌ها
۴. **گسترش آگاهی** — اشتراک‌گذاری با کسانی که ممکن است بهره‌مند شوند
۵. **اهدای منابع** — سخت‌افزار، هاستینگ، زمان توسعه

### منشور رفتاری

- این پروژه فقط برای اهداف انسان‌دوستانه است
- ما از هیچ فعالیت غیرقانونی حمایت یا تشویق نمی‌کنیم
- امنیت کاربران و اپراتورها اولویت اصلی است
- همه مشارکت‌ها باید حریم خصوصی کاربر را حفظ کنند

---

## سلب مسئولیت

⚠️ **اطلاعیه قانونی مهم**

این مخزن شامل **پیشنهاد فنی و سند بحث** است. اطلاعات ارائه شده برای اهداف آموزشی و تحقیقاتی است.

- اجرا ممکن است در برخی حوزه‌های قضایی غیرقانونی باشد
- کاربران و اپراتورها همه ریسک‌ها را می‌پذیرند
- نویسندگان هیچ ضمانتی نمی‌دهند و هیچ مسئولیتی نمی‌پذیرند
- همیشه قبل از هر اقدامی قوانین محلی را بررسی کنید
- امنیت شخصی را بالاتر از همه چیز قرار دهید

این پروژه با انگیزه حق اساسی بشر برای دسترسی به اطلاعات و ارتباط آزادانه، همانطور که در ماده ۱۹ اعلامیه جهانی حقوق بشر به رسمیت شناخته شده، ایجاد شده است.

---

## مجوز

این پروژه تحت مجوز MIT منتشر شده است - فایل [LICENSE](LICENSE) را برای جزئیات ببینید.

---

<div align="center">

**"در تاریکی، یک چراغ کافیست"**

*"In darkness, one light is enough"*

---

**جاویدنت — شبکه جاوید**

**JavidNet — The Eternal Network**

🌐 💚 🤍 ❤️

</div>

</div>

---

## 📁 Repository Structure

```
javidnet/
├── README.md                              # This file
├── LICENSE                                # MIT License
├── diagrams/
│   ├── iran-starlink-architecture.drawio  # Main architecture
│   ├── iran-starlink-dataflow.drawio      # Data flow
│   ├── iran-starlink-components.drawio    # Components
│   ├── iran-starlink-protocol-stack.drawio# Protocol stack
│   ├── iran-starlink-challenges.drawio    # Challenges
│   └── iran-starlink-bandwidth.drawio     # Bandwidth analysis
├── docs/
│   ├── technical-spec.md                  # Detailed technical specification
│   ├── security-model.md                  # Security considerations
│   └── operational-guide.md               # Operational procedures
├── src/
│   ├── bridge-server/                     # Bridge server implementation
│   ├── client/                            # Client application
│   └── relay-node/                        # Relay node software
└── research/
    ├── satellite-bypass.md                # Satellite bypass research
    ├── traffic-obfuscation.md             # Traffic obfuscation techniques
    └── related-projects.md                # Related projects and prior art
```

---

<div align="center">

**Built with ❤️ for the people**

**ساخته شده با ❤️ برای مردم**

</div>
