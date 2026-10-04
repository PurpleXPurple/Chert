# CHERT CODE LICENSE

**Supplemental Code-Specific License, Use Terms, and Scenario Register**

**Copyright (C) 2026 PurpleXPurple**

**SPDX-License-Identifier: GPL-3.0-only**

**Effective Date: 2026-02-14**

**Document Version: 1.0**

---

## PREAMBLE

This document is a supplement to, not a replacement for, the primary `LICENSE` file governing Chert. The primary `LICENSE` file contains the full text of the GNU General Public License version 3, the third-party component notices, and the Contributor License Agreement. This document exists for a different purpose: to enumerate, in exhaustive detail, what the Chert codebase is, how it may be used, how it may not be used, and what happens in specific scenarios.

This document is organized into nine sections. Sections 1 through 8 contain the substantive terms. Section 9 contains a scenario register of 340 enumerated cases covering basic use, modification, distribution, combination with other software, commercial contexts, educational contexts, jurisdictional variations, and edge cases.

**This document is not a substitute for the GPLv3.** Where this document conflicts with the GPLv3, the GPLv3 controls. Where this document is silent, the GPLv3 governs.

---

# SECTION 1: DEFINITIONS

## 1.1 Defined Terms

**1.1.1 "Chert"** means the software application known as Chert, including all source code files (`Chert.py`, `Chert_Managers.py`, `Markdown_Chert.py`, `Live_Preview.py`, `Graph_Chert.py`, `Panels_Chert.py`, `Dialogs_Chert.py`, `Theme_Chert.py`, `UI_Chert.py`), the test suite (`_stress.py`), all documentation (`Research.md`, `Audit.md`), all configuration files, and all associated materials distributed under the name "Chert."

**1.1.2 "Codebase"** means the collection of all source code files, scripts, configuration files, and build scripts that constitute Chert.

**1.1.3 "Derivative Work"** has the meaning given in GPLv3 Section 0. For the avoidance of doubt, a Derivative Work includes any work that is based on Chert or incorporates Chert in whole or in part.

**1.1.4 "Distribution"** means any act of conveying a copy of Chert, whether in source or object code form, to a third party. Distribution includes but is not limited to: publishing on a website, uploading to a repository, sending via email, pre-installing on hardware, bundling with other software, and making available over a network.

**1.1.5 "Commercial Distribution"** means Distribution in connection with a product or service for which a fee is charged, or Distribution as part of a business activity intended to generate revenue.

**1.1.6 "User"** means any individual or entity that downloads, installs, accesses, or uses Chert.

**1.1.7 "Licensor"** means the copyright holder of Chert, identified as PurpleXPurple.

**1.1.8 "PyQt6"** means the Python bindings for the Qt application framework, licensed by Riverbank Computing Limited under GPLv3 or a commercial license.

**1.1.9 "GPLv3"** means the GNU General Public License version 3, 29 June 2007, as published by the Free Software Foundation.

**1.1.10 "Corresponding Source"** has the meaning given in GPLv3 Section 1.

**1.1.11 "Object Code"** means any non-source form of Chert, including compiled bytecode, packaged executables, and installers.

**1.1.12 "Source Code"** means the preferred form of Chert for making modifications, including all Python source files and configuration scripts.

## 1.2 Interpretation

**1.2.1** Section headings are for convenience only and do not affect interpretation.

**1.2.2** "Including" means "including but not limited to."

**1.2.3** "May" means permission is granted; "must" and "shall" mean an obligation is imposed; "must not" and "may not" mean a prohibition.

**1.2.4** Singular includes plural and vice versa.

---

# SECTION 2: GRANT OF LICENSE

## 2.1 Scope of Grant

Subject to the terms of the GPLv3 and this document, the Licensor grants you a worldwide, non-exclusive, royalty-free, revocable (only as provided in GPLv3 Section 8), perpetual license to:

**2.1.1** Use Chert for any purpose, including personal, academic, commercial, and governmental purposes.

**2.1.2** Study the Source Code and understand how Chert works.

**2.1.3** Modify the Source Code and create Derivative Works.

**2.1.4** Distribute copies of Chert, modified or unmodified, in Source Code or Object Code form, provided you comply with the GPLv3.

**2.1.5** Sublicense Chert only as expressly permitted by GPLv3 Section 10.

## 2.2 Conditions Precedent

Your rights under this grant are conditioned on:

**2.2.1** Your compliance with all terms of the GPLv3.

**2.2.2** Your compliance with all terms of this document to the extent they do not conflict with the GPLv3.

**2.2.3** Your compliance with all applicable third-party license terms, including the PyQt6 GPLv3 license terms.

**2.2.4** Your not having previously had your rights terminated under GPLv3 Section 8 unless reinstated.

## 2.3 PyQt6 Constraint

**2.3.1** Chert links against PyQt6 under the GPLv3 terms offered by Riverbank Computing. Because PyQt6 is licensed as GPL-3.0-only (not "or later"), the combined work that is Chert must be distributed under GPL-3.0-only.

**2.3.2** If you wish to distribute Chert under any license other than GPL-3.0-only, you must first purchase a commercial PyQt6 license from Riverbank Computing, and you must also purchase a commercial Qt license if your chosen license is incompatible with the LGPL.

**2.3.3** The Licensor of Chert does not hold a commercial PyQt6 license. Therefore, the Licensor cannot grant you any rights beyond those permitted by the GPLv3. If you need rights beyond the GPLv3, you must obtain them from Riverbank Computing directly.

---

# SECTION 3: PERMITTED USES

## 3.1 Basic Uses

The following uses are expressly permitted, provided you comply with the GPLv3 and this document:

**3.1.1** Personal use on any number of devices you own or control.

**3.1.2** Academic use for coursework, research, and teaching.

**3.1.3** Commercial use within your own organization, without Distribution.

**3.1.4** Internal business use on company-owned devices.

**3.1.5** Use as a reference implementation for learning about PyQt6, SQLite, or force-directed graph algorithms.

**3.1.6** Use as a base for creating your own Derivative Work, provided you comply with the GPLv3.

## 3.2 Modification

**3.2.1** You may modify any part of the Source Code.

**3.2.2** You may add features, remove features, fix bugs, change the user interface, change the underlying algorithms, or make any other modification you desire.

**3.2.3** You may combine Chert with other GPL-compatible software.

**3.2.4** You may port Chert to other platforms (Linux, macOS) provided you comply with the GPLv3.

## 3.3 Distribution

**3.3.1** You may distribute verbatim copies of Chert under GPLv3 Section 4.

**3.3.2** You may distribute modified versions of Chert under GPLv3 Section 5, provided you:

(a) Mark the modified files with prominent notices stating that you changed them, with dates;

(b) License the entire modified work under GPLv3;

(c) Include the full GPLv3 text;

(d) Retain all copyright notices.

**3.3.3** You may distribute Chert in Object Code form under GPLv3 Section 6, provided you also provide the Corresponding Source.

**3.3.4** You may distribute Chert over a network under GPLv3 Section 6(d), provided you make Corresponding Source available from the same place.

**3.3.5** You may distribute Chert via peer-to-peer file sharing under GPLv3 Section 6(e).

## 3.4 Commercial Activities

**3.4.1** You may use Chert to provide consulting services, provided you do not distribute Chert itself as part of the service.

**3.4.2** You may charge for support, training, or customization of Chert, provided you comply with the GPLv3 when distributing any modified version.

**3.4.3** You may use Chert internally in a commercial enterprise without triggering distribution obligations.

**3.4.4** You may sell hardware that has Chert pre-installed, provided you comply with GPLv3 Section 6 (providing Installation Information if it is a User Product).

**3.4.5** You may use Chert as part of a SaaS offering, provided you comply with GPLv3 Section 13 if you modify Chert and make it available for network interaction.

## 3.5 Educational Uses

**3.5.1** You may use Chert in a classroom setting.

**3.5.2** You may distribute Chert to students.

**3.5.3** You may modify Chert for educational purposes and distribute the modified version to students.

**3.5.4** You may include Chert in a curriculum, provided you do not misrepresent its license terms.

---

# SECTION 4: PROHIBITED USES

## 4.1 License Violations

You must not:

**4.1.1** Distribute Chert or a Derivative Work without providing the Corresponding Source as required by GPLv3 Section 6.

**4.1.2** Distribute Chert or a Derivative Work under any license other than GPL-3.0-only, unless you hold a commercial PyQt6 license.

**4.1.3** Remove or alter any copyright notice, license notice, or disclaimer in the Source Code or documentation.

**4.1.4** Distribute Chert in Object Code form without also distributing or offering the Corresponding Source.

**4.1.5** Impose any further restrictions on the rights granted by the GPLv3.

**4.1.6** Sublicense Chert except as expressly permitted by GPLv3 Section 10.

**4.1.7** Use Chert in a manner that would require a patent license that you do not hold.

## 4.2 Unlawful Uses

You must not use Chert:

**4.2.1** To create, store, or distribute child sexual abuse material.

**4.2.2** To create, store, or distribute material that incites terrorism or violence.

**4.2.3** To violate any applicable export control or sanctions law.

**4.2.4** To infringe any third party's intellectual property rights.

**4.2.5** To violate any person's privacy rights.

**4.2.6** To engage in any activity that is illegal in your jurisdiction.

## 4.3 Malicious Uses

You must not:

**4.3.1** Introduce malicious code into Chert or any Derivative Work.

**4.3.2** Use Chert to gain unauthorized access to any system.

**4.3.3** Use Chert to conduct denial-of-service attacks.

**4.3.4** Use Chert to distribute malware.

**4.3.5** Modify Chert to include spyware, adware, or any other unwanted software.

## 4.4 High-Risk Uses

**4.4.1** Chert is not designed, tested, or certified for use in high-risk environments, including but not limited to: nuclear facilities, aircraft navigation or communication systems, air traffic control, life support systems, medical devices, or weapons systems.

**4.4.2** You must not use Chert in any application where failure could lead to death, personal injury, or severe property damage.

**4.4.3** The Licensor disclaims all liability for any use of Chert in a high-risk environment.

## 4.5 Misrepresentation

You must not:

**4.5.1** Represent that Chert is your own original work.

**4.5.2** Remove or alter the copyright notice identifying PurpleXPurple as the original author.

**4.5.3** Claim that Chert has been endorsed by the Licensor.

**4.5.4** Use the name "Chert" in a way that suggests the Licensor sponsors or endorses your product, without the Licensor's written permission.

---

# SECTION 5: COMPLIANCE OBLIGATIONS

## 5.1 General Compliance

**5.1.1** You must comply with the GPLv3 at all times.

**5.1.2** You must comply with the license terms of all third-party components, including PyQt6, Qt, Qt WebEngine, KaTeX, Mermaid, SQLite, and Python.

**5.1.3** You must keep records sufficient to demonstrate compliance with the GPLv3 and third-party licenses.

## 5.2 Source Code Compliance

**5.2.1** When you distribute Chert in Object Code form, you must provide the Corresponding Source as defined in GPLv3 Section 1.

**5.2.2** The Corresponding Source must include all scripts used to control compilation and installation of the Object Code.

**5.2.3** The Corresponding Source must be in a format that is publicly documented and requires no special password or key for unpacking, reading, or copying.

**5.2.4** If you distribute via a network server, the Corresponding Source must be available from the same server or from a server that provides equivalent access.

**5.2.5** If you distribute via physical media, the Corresponding Source must be fixed on a durable physical medium.

## 5.3 Notice Compliance

**5.3.1** You must include the full text of the GPLv3 with every distribution.

**5.3.2** You must retain all copyright notices, license notices, and disclaimers.

**5.3.3** You must prominently state that Chert is licensed under GPL-3.0-only and that it comes with no warranty.

**5.3.4** If Chert has an interactive user interface, you must display Appropriate Legal Notices as defined in GPLv3 Section 0.

## 5.4 Modification Compliance

**5.4.1** If you modify Chert, you must mark the modified files with prominent notices stating that you changed them and the date of each change.

**5.4.2** You must license the entire modified work under GPL-3.0-only.

**5.4.3** You must not impose any additional restrictions on the modified work.

## 5.5 Patent Compliance

**5.5.1** If you hold patents that cover Chert, you must grant a patent license as required by GPLv3 Section 11.

**5.5.2** If you distribute Chert while relying on a patent license, you must make the Corresponding Source available as required by GPLv3 Section 11.

**5.5.3** You must not engage in patent litigation against users of Chert as prohibited by GPLv3 Section 10.

## 5.6 Anti-Circumvention Compliance

**5.6.1** You must not assert any legal power to forbid circumvention of technological measures as prohibited by GPLv3 Section 3.

**5.6.2** You must not use Chert in a way that would make it part of an effective technological measure under anti-circumvention laws.

---

# SECTION 6: LIABILITY, WARRANTY, AND INDEMNITY

## 6.1 Disclaimer of Warranty

**6.1.1** Chert is provided "AS IS," without warranty of any kind, express or implied.

**6.1.2** THE LICENSOR DISCLAIMS ALL IMPLIED WARRANTIES, INCLUDING BUT NOT LIMITED TO THE IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, AND NON-INFRINGEMENT.

**6.1.3** THE LICENSOR DOES NOT WARRANT THAT CHERT WILL BE ERROR-FREE, UNINTERRUPTED, SECURE, OR FREE FROM VIRUSES OR OTHER HARMFUL COMPONENTS.

**6.1.4** THE LICENSOR DOES NOT WARRANT THAT CHERT WILL MEET YOUR REQUIREMENTS OR THAT ANY ERRORS IN CHERT WILL BE CORRECTED.

**6.1.5** The disclaimer of implied warranties is intended to be conspicuous as required by the Uniform Commercial Code and analogous laws in other jurisdictions.

## 6.2 Limitation of Liability

**6.2.1** TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, THE LICENSOR SHALL NOT BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES ARISING OUT OF OR RELATED TO YOUR USE OF CHERT.

**6.2.2** THIS LIMITATION APPLIES REGARDLESS OF THE LEGAL THEORY, WHETHER CONTRACT, TORT, STRICT LIABILITY, OR OTHERWISE.

**6.2.3** THE LICENSOR'S TOTAL CUMULATIVE LIABILITY SHALL NOT EXCEED THE GREATER OF (A) THE AMOUNT YOU PAID FOR CHERT (WHICH IS ZERO FOR THE FREE DISTRIBUTION) OR (B) FIVE UNITED STATES DOLLARS (USD $5.00).

**6.2.4** THE LIMITATIONS IN THIS SECTION SHALL APPLY NOTWITHSTANDING ANY FAILURE OF ESSENTIAL PURPOSE OF ANY LIMITED REMEDY.

**6.2.5** Some jurisdictions do not allow the exclusion or limitation of incidental or consequential damages. In such jurisdictions, the Licensor's liability shall be limited to the maximum extent permitted by law.

## 6.3 Indemnification

**6.3.1** You agree to defend, indemnify, and hold harmless the Licensor from any claims, damages, losses, liabilities, costs, and expenses (including reasonable attorneys' fees) arising out of or related to:

(a) Your use of Chert;

(b) Your violation of this document or the GPLv3;

(c) Your violation of any third-party right;

(d) Any Derivative Work you create.

**6.3.2** The Licensor reserves the right to assume exclusive defense and control of any matter subject to indemnification.

**6.3.3** You must cooperate with the Licensor in asserting any available defenses.

## 6.4 Data Loss

**6.4.1** The Licensor is not responsible for any loss, corruption, or unavailability of data, including notes, vaults, index databases, or settings.

**6.4.2** You are solely responsible for maintaining independent backups of all data stored in vaults accessed by Chert.

**6.4.3** The Licensor makes no representation that Chert's index databases are safe for use in synchronized folders or network shares.

## 6.5 No Support

**6.5.1** The Licensor has no obligation to provide support, updates, bug fixes, security patches, or any other form of assistance.

**6.5.2** Chert is archived and unsupported.

---

# SECTION 7: TERMINATION

## 7.1 Automatic Termination

**7.1.1** Your rights under this document and the GPLv3 terminate automatically if you breach any material term.

**7.1.2** Breach includes, but is not limited to: failing to provide Corresponding Source, removing copyright notices, or distributing under a non-GPL-compatible license without a commercial PyQt6 license.

## 7.2 Reinstatement

**7.2.1** If your rights are terminated, they may be reinstated under the conditions set forth in GPLv3 Section 8.

**7.2.2** Provisional reinstatement occurs if you cease all violations and the Licensor does not explicitly terminate your license.

**7.2.3** Permanent reinstatement occurs if you cure the violation within 30 days of receiving notice.

## 7.3 Effect of Termination

**7.3.1** Upon termination, you must cease all distribution of Chert and any Derivative Work.

**7.3.2** You must delete all copies of Chert in your possession or control.

**7.3.3** Termination does not affect the licenses of parties who received copies from you before termination.

**7.3.4** Termination does not relieve you of obligations incurred prior to termination, including indemnification obligations.

## 7.4 Survival

**7.4.1** The following sections survive termination: Section 1 (Definitions), Section 4 (Prohibited Uses), Section 5 (Compliance Obligations), Section 6 (Liability, Warranty, and Indemnity), and this Section 7.

---

# SECTION 8: THIRD-PARTY INTERACTIONS

## 8.1 PyQt6

**8.1.1** Chert depends on PyQt6. You must comply with the PyQt6 license terms.

**8.1.2** If you distribute Chert without a commercial PyQt6 license, you must comply with the GPLv3.

**8.1.3** If you hold a commercial PyQt6 license, you may distribute Chert under other terms, but you must still comply with the GPLv3 to the extent required by any GPL-licensed components.

## 8.2 Qt

**8.2.1** Chert uses Qt 6, licensed under LGPLv3, GPLv3, or commercial terms.

**8.2.2** If you distribute Chert under GPLv3, you must comply with the GPLv3 terms for Qt.

**8.2.3** If you hold a commercial Qt license, different terms apply.

## 8.3 Qt WebEngine / Chromium

**8.3.1** Chert uses Qt WebEngine, which embeds Chromium. You must comply with all Chromium third-party licenses.

**8.3.2** A complete list of Chromium third-party licenses is available in the Qt WebEngine documentation.

## 8.4 KaTeX and Mermaid

**8.4.1** Chert loads KaTeX and Mermaid from a CDN by default. Both are MIT-licensed.

**8.4.2** If you vendor these assets, you must include the MIT license texts and copyright notices.

**8.4.3** If you load from CDN, your use of the CDN is subject to the CDN's terms of service.

## 8.5 SQLite

**8.5.1** Chert uses SQLite. SQLite is in the public domain. No license obligations attach.

## 8.6 Python

**8.6.1** Chert runs on Python. If you distribute a bundled executable, you must include the PSF License Agreement and retain the Python copyright notice.

**8.7** **Combining Chert with Other Software**

**8.7.1** You may combine Chert with GPL-compatible software without restriction.

**8.7.2** You may not combine Chert with proprietary software in a way that creates a single combined work unless you hold a commercial PyQt6 license or the proprietary software is a separate work communicating at arm's length.

**8.7.3** Aggregating Chert with other independent works on a storage medium does not cause the GPLv3 to apply to the other works.

---

# SECTION 9: SCENARIO REGISTER

This section enumerates 340 specific scenarios, organized by category. Each scenario states a fact pattern and the applicable rule. This section is illustrative, not exhaustive. The absence of a scenario does not imply permission.

## 9.1 Personal Use Scenarios (1–40)

1. You install Chert on your personal laptop. **Permitted.** No distribution. No obligations triggered.
2. You install Chert on your work laptop. **Permitted** for internal use. No distribution.
3. You install Chert on five personal devices. **Permitted.** The GPLv3 does not limit the number of installations.
4. You use Chert to write personal notes. **Permitted.** User content is not restricted.
5. You use Chert to store passwords in plaintext. **Permitted**, but insecure. The Licensor disclaims liability for data loss.
6. You use Chert to store illegal content. **Prohibited.** You are responsible for content legality.
7. You use Chert to store child sexual abuse material. **Absolutely prohibited.** No legal or educational framing exists.
8. You use Chert to store terrorism-related material. **Prohibited.**
9. You use Chert to store copyrighted material you do not own. **Prohibited** if it constitutes infringement in your jurisdiction.
10. You use Chert to store medical records. **Permitted**, but you are responsible for compliance with HIPAA and analogous laws.
11. You use Chert to store financial records. **Permitted**, but you are responsible for compliance with applicable financial regulations.
12. You use Chert to store legal documents. **Permitted.** No restriction on content type.
13. You use Chert to store client data. **Permitted**, but you are responsible for data protection compliance.
14. You use Chert to store trade secrets. **Permitted.** The Licensor does not access your data.
15. You use Chert with a vault on a network share. **Permitted**, but the Licensor warns that index databases may corrupt.
16. You use Chert with a vault on a USB drive. **Permitted.** No restriction on storage location.
17. You use Chert with a vault on a cloud-synced folder. **Permitted**, but see Scenario 15 warning.
18. You use Chert with a vault on a read-only filesystem. **Permitted**, but index writes will fail. The error router will report the failure and continue.
19. You use Chert with a vault containing 100,000 notes. **Permitted**, but performance may degrade.
20. You use Chert with a vault containing only one note. **Permitted.** The graph will show a single node.
21. You use Chert with an empty vault. **Permitted.** The file tree will be empty.
22. You use Chert to open a vault on a remote server via SSHFS. **Permitted**, but performance may be poor.
23. You use Chert to open a vault on a mounted network drive. **Permitted**, with the same warning as Scenario 15.
24. You use Chert to edit notes in a Git repository. **Permitted.** The `.chert` directory may need to be gitignored.
25. You use Chert to edit notes in a Mercurial repository. **Permitted.** Same note as Scenario 24.
26. You use Chert to edit notes in an SVN working copy. **Permitted.**
27. You use Chert to edit notes in a Dropbox folder. **Permitted**, with the sync warning.
28. You use Chert to edit notes in a Google Drive folder. **Permitted**, with the sync warning.
29. You use Chert to edit notes in a OneDrive folder. **Permitted**, with the sync warning.
30. You use Chert to edit notes in an iCloud Drive folder. **Permitted**, with the sync warning.
31. You use Chert on Windows 10. **Permitted.** Chert is Windows-first.
32. You use Chert on Windows 11. **Permitted.**
33. You use Chert on Windows 8.1. **Not tested.** May work, no guarantee.
34. You use Chert on Windows 7. **Not tested.** May work if PyQt6 supports it.
35. You use Chert on Linux. **Permitted** if you install PyQt6 and resolve platform differences. The code is not tested on Linux.
36. You use Chert on macOS. **Permitted** if you install PyQt6 and resolve platform differences. The code is not tested on macOS.
37. You use Chert on a 32-bit Python interpreter. **Not supported.** PyQt6 wheels are 64-bit only. The `requirements.txt` mentions a PyQt5 fallback that does not exist.
38. You use Chert on Python 3.7. **Not supported.** The code uses features that require Python 3.8+.
39. You use Chert on Python 3.12. **Permitted**, assuming PyQt6 supports it.
40. You use Chert on PyPy. **Not supported.** PyQt6 is CPython-only.

## 9.2 Modification Scenarios (41–80)

41. You fix a typo in a comment. **Permitted.** Mark the change.
42. You fix a bug in the Markdown renderer. **Permitted.** Mark the change and license under GPLv3.
43. You add a new theme. **Permitted.** The theme file becomes part of the Derivative Work.
44. You add a new panel. **Permitted.**
45. You add a new GraphBuilder method. **Permitted.**
46. You remove a feature you do not use. **Permitted.**
47. You remove the graph view entirely. **Permitted.**
48. You replace the SQLite backend with PostgreSQL. **Permitted**, provided you comply with the GPLv3.
49. You replace QWebEngine with a different preview engine. **Permitted.**
50. You replace PyQt6 with PySide6. **Permitted.** PySide6 is LGPLv3, which is GPLv3-compatible. Your Derivative Work would still be GPLv3.
51. You port Chert to Rust. **Permitted.** The port is a Derivative Work under GPLv3.
52. You port Chert to JavaScript/Electron. **Permitted.** The port is a Derivative Work under GPLv3.
53. You rewrite Chert from scratch, inspired by its architecture. **Permitted** if the rewrite does not copy expression. If it copies source code, it is a Derivative Work.
54. You change the application name from Chert to something else. **Permitted**, but you must retain the copyright notice and license.
55. You change the copyright notice to your own name. **Prohibited.** You must retain the original copyright notice and add your own.
56. You remove the copyright notice. **Prohibited.**
57. You remove the GPLv3 license text. **Prohibited.**
58. You change the license to MIT. **Prohibited** without a commercial PyQt6 license.
59. You change the license to Apache 2.0. **Prohibited** without a commercial PyQt6 license.
60. You change the license to proprietary. **Prohibited** without a commercial PyQt6 license.
61. You add a "no commercial use" restriction. **Prohibited.** The GPLv3 does not permit additional restrictions.
62. You add a "no military use" restriction. **Prohibited.** The GPLv3 does not permit additional restrictions.
63. You add a "no ethical use" restriction. **Prohibited.** The GPLv3 does not permit additional restrictions.
64. You add an arbitration clause. **Prohibited** if it imposes a further restriction on GPL rights.
65. You add a class action waiver. **Prohibited** if it imposes a further restriction on GPL rights.
66. You add a choice of law clause. **Permitted** if it does not restrict GPL rights.
67. You add a disclaimer of warranty that differs from GPLv3 Sections 15 and 16. **Permitted** under GPLv3 Section 7(a) if you have copyright permission, but you cannot reduce the rights of downstream recipients.
68. You add an attribution requirement for your own contributions. **Permitted** under GPLv3 Section 7(b).
69. You prohibit misrepresentation of origin. **Permitted** under GPLv3 Section 7(c).
70. You limit the use of your name for publicity. **Permitted** under GPLv3 Section 7(d).
71. You decline to grant trademark rights. **Permitted** under GPLv3 Section 7(e).
72. You require indemnification from distributors. **Permitted** under GPLv3 Section 7(f).
73. You add any other restriction. **Prohibited** as a "further restriction" under GPLv3 Section 10.
74. You use Chert as a library in another GPL project. **Permitted.**
75. You use Chert as a library in a proprietary project. **Prohibited** without a commercial PyQt6 license.
76. You use Chert as a library in an LGPL project. **Permitted** if the LGPL project can comply with GPLv3 for the combined work. If the LGPL project cannot, you need a commercial PyQt6 license.
77. You use Chert as a library in an MIT project. **Prohibited** without a commercial PyQt6 license, because MIT is GPL-incompatible for combined works.
78. You use Chert as a library in an Apache 2.0 project. **Prohibited** without a commercial PyQt6 license, because Apache 2.0 has patent terms that are GPLv3-compatible only if you do not impose additional restrictions.
79. You use Chert as a library in an AGPL project. **Permitted.** AGPLv3 is GPLv3-compatible under GPLv3 Section 13.
80. You use Chert as a library in a BSD project. **Prohibited** without a commercial PyQt6 license, same reasoning as MIT.

## 9.3 Distribution Scenarios (81–130)

81. You upload Chert to GitHub. **Permitted**, provided the repository includes the full GPLv3 license text.
82. You upload Chert to GitLab. **Permitted.**
83. You upload Chert to Bitbucket. **Permitted.**
84. You upload Chert to SourceForge. **Permitted.**
85. You upload Chert to a personal website. **Permitted.**
86. You upload Chert to a corporate intranet. **Permitted** for internal distribution.
87. You upload Chert to a public file-sharing service. **Permitted.**
88. You send Chert via email to a colleague. **Permitted**, but you must include the license.
89. You send Chert via email to a mailing list. **Permitted**, but you must include the license.
90. You post Chert on a forum. **Permitted**, but you must include the license.
91. You post Chert on Reddit. **Permitted**, but you must include the license.
92. You post Chert on Hacker News. **Permitted**, but you must include the license.
93. You share Chert via a torrent. **Permitted** under GPLv3 Section 6(e).
94. You share Chert via a magnet link. **Permitted** under GPLv3 Section 6(e).
95. You share Chert via IPFS. **Permitted** under GPLv3 Section 6(d) if you make source available.
96. You distribute Chert on a USB stick. **Permitted**, but you must include the source and license.
97. You distribute Chert on a CD-ROM. **Permitted**, same requirement.
98. You distribute Chert on a DVD. **Permitted**, same requirement.
99. You distribute Chert pre-installed on a laptop. **Permitted**, but if it is a User Product, you must provide Installation Information under GPLv3 Section 6.
100. You distribute Chert pre-installed on a server. **Permitted.** Servers are generally not User Products.
101. You distribute Chert pre-installed on a phone. **Permitted**, but User Product rules may apply.
102. You distribute Chert pre-installed on a tablet. **Permitted**, same caveat.
103. You distribute Chert pre-installed on an IoT device. **Permitted**, but User Product rules may apply if it is a consumer product.
104. You distribute Chert as part of a Docker image. **Permitted**, but you must include the source and license.
105. You distribute Chert as part of a Snap package. **Permitted**, same requirement.
106. You distribute Chert as part of a Flatpak. **Permitted**, same requirement.
107. You distribute Chert as part of an AppImage. **Permitted**, same requirement.
108. You distribute Chert as part of a Windows installer. **Permitted**, same requirement.
109. You distribute Chert as part of an MSI package. **Permitted**, same requirement.
110. You distribute Chert as part of a Debian package. **Permitted**, same requirement.
111. You distribute Chert as part of an RPM package. **Permitted**, same requirement.
112. You distribute Chert as part of an Arch package. **Permitted**, same requirement.
113. You distribute Chert on the Microsoft Store. **Permitted**, provided you comply with Microsoft's terms and the GPLv3.
114. You distribute Chert on the Apple App Store. **Prohibited** because Apple's terms impose restrictions incompatible with GPLv3.
115. You distribute Chert on Google Play. **Permitted** if Google's terms do not impose incompatible restrictions.
116. You distribute Chert on F-Droid. **Permitted.**
117. You distribute Chert on Steam. **Permitted** if Steam's terms do not impose incompatible restrictions.
118. You distribute Chert on Itch.io. **Permitted.**
119. You distribute Chert on GOG. **Permitted** if GOG's terms do not impose incompatible restrictions.
120. You distribute Chert as part of a commercial software bundle. **Permitted**, but the entire bundle must comply with GPLv3 if Chert is a combined work.
121. You distribute Chert as a standalone commercial product. **Permitted**, but you must comply with GPLv3.
122. You sell Chert on eBay. **Permitted**, but you must include the source and license.
123. You sell Chert on Craigslist. **Permitted**, same requirement.
124. You sell Chert on Etsy. **Permitted**, same requirement.
125. You sell Chert on a personal storefront. **Permitted**, same requirement.
126. You sell Chert on Gumroad. **Permitted**, same requirement.
127. You sell Chert on Paddle. **Permitted**, same requirement.
128. You sell Chert on Stripe. **Permitted**, same requirement.
129. You sell Chert on PayPal. **Permitted**, same requirement.
130. You sell Chert on Patreon. **Permitted**, same requirement.

## 9.4 Commercial Scenarios (131–180)

131. You use Chert internally at a for-profit company. **Permitted** without distribution.
132. You use Chert internally at a non-profit. **Permitted.**
133. You use Chert internally at a government agency. **Permitted.**
134. You use Chert internally at a military organization. **Permitted** for internal use, but export control laws may apply.
135. You use Chert to provide consulting services to clients. **Permitted**, provided you do not distribute Chert itself.
136. You use Chert to provide training services. **Permitted**, provided you do not distribute Chert without source.
137. You use Chert to provide support services. **Permitted**, same requirement.
138. You use Chert to develop custom software for a client. **Permitted**, but if you distribute the custom software with Chert, you must comply with GPLv3.
139. You use Chert as part of a SaaS offering. **Permitted**, but if you modify Chert and make it available over a network, GPLv3 Section 13 applies.
140. You use Chert as part of a PaaS offering. **Permitted**, same caveat.
141. You use Chert as part of an IaaS offering. **Permitted**, same caveat.
142. You use Chert to process customer data. **Permitted**, but you are responsible for data protection compliance.
143. You use Chert to process employee data. **Permitted**, same caveat.
144. You use Chert to process health data. **Permitted**, but HIPAA may apply.
145. You use Chert to process financial data. **Permitted**, but financial regulations may apply.
146. You use Chert to process children's data. **Permitted**, but COPPA and analogous laws may apply.
147. You use Chert to process biometric data. **Permitted**, but BIPA and analogous laws may apply.
148. You use Chert to process location data. **Permitted**, but privacy laws may apply.
149. You use Chert to process EU personal data. **Permitted**, but GDPR may apply to your processing, not to Chert itself.
150. You use Chert to process California personal data. **Permitted**, but CCPA/CPRA may apply to your processing.
151. You use Chert to process Chinese personal data. **Permitted**, but PIPL may apply to your processing.
152. You use Chert to process Brazilian personal data. **Permitted**, but LGPD may apply to your processing.
153. You use Chert to process Indian personal data. **Permitted**, but DPDP Act may apply to your processing.
154. You use Chert to process Japanese personal data. **Permitted**, but APPI may apply to your processing.
155. You use Chert to process South Korean personal data. **Permitted**, but PIPA may apply to your processing.
156. You use Chert to process Russian personal data. **Permitted**, but data localization laws may apply.
157. You use Chert to process Australian personal data. **Permitted**, but Privacy Act may apply to your processing.
158. You use Chert to process Canadian personal data. **Permitted**, but PIPEDA may apply to your processing.
159. You use Chert to process UK personal data. **Permitted**, but UK GDPR may apply to your processing.
160. You sell a product that includes Chert. **Permitted**, provided you comply with GPLv3 for Chert.
161. You sell a product that links against Chert. **Permitted**, provided the combined work is GPLv3.
162. You sell a product that imports Chert as a Python module. **Permitted**, provided the combined work is GPLv3.
163. You sell a product that bundles Chert as a separate executable. **Permitted** if they communicate at arm's length, but the executable itself remains GPLv3.
164. You sell a product that calls Chert via subprocess. **Permitted** if they are separate works, but the Chert executable remains GPLv3.
165. You sell a product that calls Chert via RPC. **Permitted** if they are separate works.
166. You sell a product that calls Chert via HTTP. **Permitted** if they are separate works.
167. You sell a product that shares data with Chert via a file. **Permitted** if they are separate works.
168. You sell a product that shares data with Chert via a database. **Permitted** if they are separate works.
169. You sell a product that shares data with Chert via shared memory. **Permitted** if they are separate works.
170. You sell a product that shares data with Chert via a pipe. **Permitted** if they are separate works.
171. You sell a product that shares data with Chert via a socket. **Permitted** if they are separate works.
172. You sell a product that shares data with Chert via a message queue. **Permitted** if they are separate works.
173. You sell a product that links Chert statically. **Prohibited** without a commercial PyQt6 license, because static linking creates a combined work.
174. You sell a product that links Chert dynamically. **Permitted** if the dynamic linking does not create a combined work, but the GPLv3 analysis is fact-specific.
175. You sell a product that includes Chert's source code. **Permitted**, provided the product is GPLv3.
176. You sell a product that includes Chert's object code. **Permitted**, provided you provide the Corresponding Source.
177. You sell a product that includes Chert's documentation. **Permitted**, provided you include the license.
178. You sell a product that includes Chert's test suite. **Permitted**, provided you include the license.
179. You sell a product that includes Chert's configuration files. **Permitted**, provided you include the license.
180. You sell a product that includes Chert's build scripts. **Permitted**, provided you include the license.

## 9.5 Educational Scenarios (181–220)

181. You use Chert in a university course. **Permitted.**
182. You use Chert in a high school course. **Permitted.**
183. You use Chert in a primary school course. **Permitted**, subject to COPPA if applicable.
184. You use Chert in a MOOC. **Permitted.**
185. You use Chert in a coding bootcamp. **Permitted.**
186. You use Chert in a corporate training program. **Permitted.**
187. You use Chert in a workshop. **Permitted.**
188. You use Chert in a seminar. **Permitted.**
189. You use Chert in a conference presentation. **Permitted.**
190. You use Chert in a research project. **Permitted.**
191. You use Chert to analyze research data. **Permitted.**
192. You use Chert to write a research paper. **Permitted.**
193. You use Chert to write a thesis. **Permitted.**
194. You use Chert to write a dissertation. **Permitted.**
195. You use Chert to teach a class. **Permitted.**
196. You use Chert to grade papers. **Permitted**, but FERPA may apply to student data.
197. You use Chert to store student records. **Permitted**, but FERPA may apply.
198. You use Chert to store grades. **Permitted**, but FERPA may apply.
199. You use Chert to store attendance records. **Permitted**, but FERPA may apply.
200. You use Chert to store disciplinary records. **Permitted**, but FERPA may apply.
201. You distribute Chert to students. **Permitted.**
202. You distribute a modified version of Chert to students. **Permitted**, provided you comply with GPLv3.
203. You assign students to modify Chert. **Permitted.**
204. You assign students to distribute their modifications. **Permitted**, provided they comply with GPLv3.
205. You include Chert in a textbook. **Permitted**, provided you include the license.
206. You include Chert in a course pack. **Permitted**, provided you include the license.
207. You include Chert in an online course. **Permitted**, provided you include the license.
208. You include Chert in a video lecture. **Permitted**, provided you include the license.
209. You include Chert in a podcast. **Permitted**, provided you include the license.
210. You include Chert in a YouTube tutorial. **Permitted**, provided you include the license.
211. You include Chert in a Twitch stream. **Permitted**, provided you include the license.
212. You include Chert in a blog post. **Permitted**, provided you include the license.
213. You include Chert in a newsletter. **Permitted**, provided you include the license.
214. You include Chert in a magazine article. **Permitted**, provided you include the license.
215. You include Chert in a newspaper article. **Permitted**, provided you include the license.
216. You include Chert in an academic paper. **Permitted**, provided you include the license.
217. You include Chert in a conference paper. **Permitted**, provided you include the license.
218. You include Chert in a journal article. **Permitted**, provided you include the license.
219. You include Chert in a book. **Permitted**, provided you include the license.
220. You include Chert in a thesis. **Permitted**, provided you include the license.

## 9.6 Jurisdictional Scenarios (221–260)

221. You are in the United States. **GPLv3 governs.** Warranty disclaimers are enforceable if conspicuous.
222. You are in the European Union. **GPLv3 governs**, but consumer protection laws may limit warranty disclaimers against consumers.
223. You are in the United Kingdom. **GPLv3 governs**, similar consumer protection caveat.
224. You are in Germany. **GPLv3 governs.** German courts have enforced GPLv3.
225. You are in France. **GPLv3 governs.** French courts have awarded damages for GPL violations.
226. You are in Italy. **GPLv3 governs.**
227. You are in Spain. **GPLv3 governs.**
228. You are in the Netherlands. **GPLv3 governs.**
229. You are in Belgium. **GPLv3 governs.**
230. You are in Switzerland. **GPLv3 governs.**
231. You are in Norway. **GPLv3 governs.**
232. You are in Sweden. **GPLv3 governs.**
233. You are in Denmark. **GPLv3 governs.**
234. You are in Finland. **GPLv3 governs.**
235. You are in Poland. **GPLv3 governs.**
236. You are in the Czech Republic. **GPLv3 governs.**
237. You are in Austria. **GPLv3 governs.**
238. You are in Ireland. **GPLv3 governs.**
239. You are in Portugal. **GPLv3 governs.**
240. You are in Greece. **GPLv3 governs.**
241. You are in Turkey. **GPLv3 governs.**
242. You are in Russia. **GPLv3 governs**, but enforcement may be uncertain.
243. You are in China. **GPLv3 governs.** Chinese courts have recognized GPLv3 as a contract.
244. You are in India. **GPLv3 governs.**
245. You are in Japan. **GPLv3 governs.**
246. You are in South Korea. **GPLv3 governs.**
247. You are in Australia. **GPLv3 governs.**
248. You are in New Zealand. **GPLv3 governs.**
249. You are in Canada. **GPLv3 governs.**
250. You are in Mexico. **GPLv3 governs.**
251. You are in Brazil. **GPLv3 governs.**
252. You are in Argentina. **GPLv3 governs.**
253. You are in Chile. **GPLv3 governs.**
254. You are in Colombia. **GPLv3 governs.**
255. You are in Egypt. **GPLv3 governs.** Egyptian copyright law applies.
256. You are in South Africa. **GPLv3 governs.**
257. You are in Nigeria. **GPLv3 governs.**
258. You are in Kenya. **GPLv3 governs.**
259. You are in Israel. **GPLv3 governs.**
260. You are in the United Arab Emirates. **GPLv3 governs.**

## 9.7 Edge Cases and Adversarial Scenarios (261–300)

261. You distribute Chert without the license text. **Violation.** You must include the license.
262. You distribute Chert without the copyright notice. **Violation.** You must retain the notice.
263. You distribute Chert under a different name without attribution. **Violation.**
264. You distribute Chert with a EULA that restricts reverse engineering. **Violation.** The GPLv3 permits reverse engineering.
265. You distribute Chert with a EULA that prohibits commercial use. **Violation.** The GPLv3 permits commercial use.
266. You distribute Chert with a EULA that prohibits redistribution. **Violation.** The GPLv3 permits redistribution.
267. You distribute Chert with a EULA that requires payment for redistribution. **Violation.**
268. You distribute Chert with a EULA that imposes a royalty. **Violation.**
269. You distribute Chert with a EULA that imposes a patent cross-license. **Violation** if it is a further restriction.
270. You distribute Chert with a EULA that requires arbitration. **Violation** if it restricts GPL rights.
271. You distribute Chert with a EULA that requires class action waiver. **Violation** if it restricts GPL rights.
272. You distribute Chert with a EULA that requires choice of law in a jurisdiction that does not enforce GPLv3. **Violation.**
273. You distribute Chert with a EULA that requires choice of forum in a jurisdiction that does not enforce GPLv3. **Violation.**
274. You distribute Chert with a EULA that limits liability more than GPLv3 Sections 15 and 16. **Violation** if it reduces downstream rights.
275. You distribute Chert with a EULA that disclaims warranties more broadly than GPLv3 Sections 15 and 16. **Permitted** if you have copyright permission.
276. You distribute Chert with a EULA that adds an attribution requirement. **Permitted** under GPLv3 Section 7(b).
277. You distribute Chert with a EULA that prohibits misrepresentation. **Permitted** under GPLv3 Section 7(c).
278. You distribute Chert with a EULA that limits publicity rights. **Permitted** under GPLv3 Section 7(d).
279. You distribute Chert with a EULA that declines trademark rights. **Permitted** under GPLv3 Section 7(e).
280. You distribute Chert with a EULA that requires indemnification. **Permitted** under GPLv3 Section 7(f).
281. You distribute Chert with a EULA that imposes any other restriction. **Violation** as a further restriction.
282. You modify Chert and claim you wrote it from scratch. **Violation.** You must mark modifications.
283. You modify Chert and remove the modification notices. **Violation.**
284. You modify Chert and change the copyright notice to your own. **Violation.**
285. You modify Chert and add your own copyright notice alongside the original. **Permitted.**
286. You modify Chert and license it under MIT. **Violation** without a commercial PyQt6 license.
287. You modify Chert and license it under Apache 2.0. **Violation** without a commercial PyQt6 license.
288. You modify Chert and license it under BSD. **Violation** without a commercial PyQt6 license.
289. You modify Chert and license it under proprietary terms. **Violation** without a commercial PyQt6 license.
290. You modify Chert and distribute it without source. **Violation.**
291. You modify Chert and distribute it with source but no license. **Violation.**
292. You modify Chert and distribute it with source and license but no modification notices. **Violation.**
293. You modify Chert and distribute it with source, license, and modification notices. **Compliant.**
294. You modify Chert and distribute it via a network server, making it available for interaction. **Permitted**, but GPLv3 Section 13 applies. You must make source available to network users.
295. You modify Chert and distribute it via a network server, but you do not make it available for interaction. **Permitted** under GPLv3 Section 6(d), provided source is available.
296. You modify Chert and distribute it via a network server, making it available for interaction, but you do not make source available to network users. **Violation** of GPLv3 Section 13.
297. You use Chert to build a proprietary application and distribute it. **Violation** without a commercial PyQt6 license.
298. You use Chert to build a proprietary application and do not distribute it. **Permitted.** GPL obligations attach on distribution.
299. You use Chert to build a proprietary application and distribute it only within your organization. **Permitted** if all recipients are within the same legal entity.
300. You use Chert to build a proprietary application and distribute it to contractors. **Violation** unless the contractors are within the same legal entity or you have a commercial PyQt6 license.

## 9.8 Combination and Compatibility Scenarios (301–340)

301. You combine Chert with MIT-licensed code. **Permitted.** The MIT code remains MIT; Chert remains GPLv3.
302. You combine Chert with BSD-licensed code. **Permitted.** The BSD code remains BSD; Chert remains GPLv3.
303. You combine Chert with Apache 2.0 code. **Permitted**, provided the Apache code's patent terms do not impose further restrictions. If they do, you need to handle it.
304. You combine Chert with GPLv2 code. **Prohibited.** GPLv2-only is incompatible with GPLv3.
305. You combine Chert with GPLv3 code. **Permitted.** Both remain GPLv3.
306. You combine Chert with LGPLv2.1 code. **Permitted** if you comply with LGPLv2.1's conversion-to-GPLv3 clause.
307. You combine Chert with LGPLv3 code. **Permitted.** Both remain GPLv3.
308. You combine Chert with AGPLv3 code. **Permitted** under GPLv3 Section 13. The combined work is AGPLv3.
309. You combine Chert with CDDL code. **Prohibited.** CDDL is incompatible with GPLv3.
310. You combine Chert with EPL code. **Prohibited.** EPL is incompatible with GPLv3.
311. You combine Chert with MPL 2.0 code. **Permitted** if you comply with MPL 2.0's secondary license provisions.
312. You combine Chert with proprietary code. **Prohibited** as a combined work without a commercial PyQt6 license.
313. You link Chert statically with proprietary code. **Prohibited** without a commercial PyQt6 license.
314. You link Chert dynamically with proprietary code. **Permitted** if the dynamic linking does not create a combined work.
315. You use Chert as a subprocess from proprietary code. **Permitted** if they are separate works.
316. You use Chert as a service from proprietary code. **Permitted** if they are separate works.
317. You use Chert as a library from proprietary code. **Prohibited** without a commercial PyQt6 license.
318. You use Chert as a plugin from proprietary code. **Permitted** if the plugin interface is at arm's length.
319. You use Chert as a plugin host for proprietary plugins. **Permitted** if the plugins are separate works.
320. You use Chert's source code in a proprietary product. **Prohibited** without a commercial PyQt6 license.
321. You use Chert's object code in a proprietary product. **Prohibited** without a commercial PyQt6 license.
322. You use Chert's documentation in a proprietary product. **Permitted** if the documentation is separately licensed or if you comply with GPLv3 for the combined work.
323. You use Chert's test suite in a proprietary product. **Prohibited** without a commercial PyQt6 license.
324. You use Chert's configuration files in a proprietary product. **Prohibited** without a commercial PyQt6 license.
325. You use Chert's build scripts in a proprietary product. **Prohibited** without a commercial PyQt6 license.
326. You use Chert's themes in a proprietary product. **Prohibited** without a commercial PyQt6 license.
327. You use Chert's icons in a proprietary product. **Prohibited** without a commercial PyQt6 license.
328. You use Chert's name in a proprietary product. **Prohibited** if it suggests endorsement.
329. You use Chert's logo in a proprietary product. **Prohibited** if it suggests endorsement.
330. You use Chert's architecture as inspiration for a clean-room reimplementation. **Permitted** if you do not copy expression.
331. You use Chert's algorithms as inspiration for a clean-room reimplementation. **Permitted** if you do not copy expression.
332. You use Chert's data structures as inspiration for a clean-room reimplementation. **Permitted** if you do not copy expression.
333. You use Chert's error handling patterns as inspiration for a clean-room reimplementation. **Permitted** if you do not copy expression.
334. You use Chert's UI layout as inspiration for a clean-room reimplementation. **Permitted** if you do not copy expression.
335. You use Chert's SQL schema as inspiration for a clean-room reimplementation. **Permitted** if you do not copy expression.
336. You use Chert's regex patterns as inspiration for a clean-room reimplementation. **Permitted** if you do not copy expression.
337. You use Chert's CSS as inspiration for a clean-room reimplementation. **Permitted** if you do not copy expression.
338. You use Chert's documentation as inspiration for a clean-room reimplementation. **Permitted** if you do not copy expression.
339. You use Chert's test cases as inspiration for a clean-room reimplementation. **Permitted** if you do not copy expression.
340. You copy Chert's source code verbatim into a proprietary product. **Prohibited** without a commercial PyQt6 license.

---

# SECTION 10: MISCELLANEOUS

## 10.1 Severability

If any provision of this document is held to be invalid or unenforceable, that provision shall be modified to the minimum extent necessary to make it valid and enforceable. If modification is not possible, the provision shall be severed, and the remaining provisions shall remain in full force and effect.

## 10.2 Entire Agreement

This document, together with the primary `LICENSE` file and the GPLv3, constitutes the entire agreement between you and the Licensor concerning Chert. It supersedes all prior or contemporaneous agreements.

## 10.3 No Waiver

The Licensor's failure to enforce any provision of this document shall not constitute a waiver of that provision or any other provision.

## 10.4 Governing Law

This document shall be governed by the laws of the jurisdiction in which the Licensor resides, without regard to conflict-of-law provisions. The GPLv3 is a global license and is enforceable in any jurisdiction that recognizes copyright.

## 10.5 Contact

For questions regarding this document, contact the Licensor at the repository identified in the primary `LICENSE` file.

## 10.6 Effective Date

This document is effective as of 2026-02-14.

---
