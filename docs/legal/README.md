# ChamaCore Legal & Commercial Documentation Checklist

> [!CAUTION]
> **DISCLAIMER: NOT LEGAL ADVICE**  
> The documents referenced and structured in this directory are placeholders and checklists for technical and operational alignment. All final legal contracts, Terms of Service, and Data Protection policies must be reviewed, drafted, and approved by qualified legal counsel licensed in Kenya before publication to production users.

---

## 1. Production Legal Readiness Checklist

Before onboarding real Chama funds and external users in production, ensure the following agreements and policies are executed:

| # | Document | Purpose | Status | Target Audience / Parties | Responsible Owner |
|---|---|---|---|---|---|
| **1** | **Terms of Service (ToS)** | Acceptable use, account obligations, liability limitations, dispute resolution | Draft Placeholder | All registered users and group members | Legal Counsel |
| **2** | **Privacy Policy** | Data collection notice, KDPA 2019 compliance, rights to access/deletion | Draft Placeholder | All platform visitors and members | Data Protection Officer / Legal |
| **3** | **Data Processing Agreement (DPA)** | Governs ChamaCore as a data processor for registered savings groups | Required for B2B / Formal SACCOs | Chama Leadership & Platform Operator | Legal Counsel |
| **4** | **Payment & Refund Policy** | M-Pesa error handling, duplicate payment claims, withdrawal timelines | Draft Placeholder | Members contributing via M-Pesa | Product & Finance Lead |
| **5** | **Master Service Agreement (MSA)** | Enterprise / Institutional Chama platform access agreements | Optional (B2B SaaS) | Registered Co-operatives / Banks | Commercial Lead |
| **6** | **Cyber Liability Insurance** | Coverage for data breach, system failure, or payment fraud | Verification Stage | Underwriting Partner | Operations / Founders |

---

## 2. Key Regulatory Touchpoints for Kenya

1. **Kenya Data Protection Act (KDPA) 2019:**
   - Registration with the Office of the Data Protection Commissioner (ODPC) as Data Controller / Data Processor.
   - Mechanism for Data Subject Access Requests (DSAR) and Right to Erasure (aligned with [`docs/DATA_RETENTION.md`](../DATA_RETENTION.md)).
2. **National Payment System Act & Central Bank of Kenya (CBK):**
   - Operating under Safaricom Daraja merchant guidelines.
   - Strict separation of customer funds in designated escrow / commercial bank accounts.
3. **Anti-Money Laundering (POCAMLA):**
   - Retention of transactional records for at least seven (7) years.
   - Verification of member national identity and government ID records.

---

## 3. Placeholders & Client Links

Frontend and mobile clients should reference the following public routes:
- `/terms` $\to$ Terms of Service
- `/privacy` $\to$ Privacy Policy
- `/refunds` $\to$ Refund & Payment Dispute Policy
