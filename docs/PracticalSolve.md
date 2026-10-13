## Latest backend tip

**`main` = `4c1ede8`** — added `docs/Practical.md` (ChamaPoint-style guide: track contributions without Excel).

Also recent: production readiness / ops docs (`7f91454`).

---

## The file: `docs/Practical.md`

It is a **treasurer practice guide** (sourced from ChamaPoint), not code. Core payment idea:

| Guide step | Meaning for Paybill |
|------------|---------------------|
| **Give every member a number** | Permanent ID (e.g. `UM001`) on every record |
| **Paybill + account number** | Members pay **group Paybill** and enter **member number as Account** |
| **One row per payment** | Date, member no., type, amount, M-Pesa ref |
| **Separate types** | Contribution vs fine vs loan repayment |
| **Monthly reconcile** | Register total ↔ bank/paybill statement |

That is the industry pattern for C2B: **BillRefNumber = member account number**.

---

## How ChamaCore already models this

| Concept | ChamaCore today |
|---------|-----------------|
| Unique seat in a Chama | `Membership` with `membership_number` (**int**, unique per `chama_id`) |
| Person | `Member` (phone + national ID global) |
| Paybill binding | `PaymentConnection` → **one shortcode ↔ one Chama** |
| C2B account number | **`BillRefNumber` = string of `membership_number`** (`c2b_payment.py` OQ-021) |
| Validate | ACTIVE connection, shortcode match, BillRef parses to int, ACTIVE membership in **that** Chama |
| Confirm | Idempotent by `TransID`; create/settle **contribution** for current `YYYY-MM` |

So the **design already matches the guide**: member number = Paybill account number, scoped per Chama.

```text
Member pays:  Paybill {BusinessShortCode}  Account {membership_number}
System:       connection.chama_id + BillRef → Membership → contribution/ledger
```

---

## Compare: guide vs your system

| Need | Guide | ChamaCore | Gap? |
|------|--------|-----------|------|
| Unique ID per member **in each Chama** | Yes (UM001…) | Yes (`membership_number`, unique per chama) | **Mostly done** |
| Use that number as M-Pesa **Account** | Yes | Yes (C2B BillRef = number) | **Done in backend** |
| Show number to members clearly | Emphasized | Depends on API/UI exposure | **Product/UX gap** |
| Account updates when membership changes | Permanent number | Number fixed at create; status ACTIVE/INACTIVE | OK if number never reused |
| Shared Paybill for many Chamas | Not covered | **One connection = one Chama** | If one shortcode for all groups → **must encode Chama in BillRef** |
| Fines / loans via same Paybill | Separate “Type” | C2B path posts as **contribution** only | **Type discrimination gap** |
| STK Push | App-initiated | Uses phone + intent; AccountReference may not be membership number | Align STK AccountReference with same number for statements |

---

## Why Paybill “feels broken”

Common causes given this architecture:

1. **Member does not know / use their `membership_number`** as Account → validation reject or wrong person.
2. **Wrong shortcode** or inactive connection → reject.
3. **Number format**: system expects **digits only** (`int(BillRef)`). `UM001` would **fail** today unless you strip prefix or change parser.
4. **STK works, C2B does not** (or reverse) because STK does not rely on BillRef the same way.
5. **Multi-Chama, one Paybill**: current model assumes **shortcode identifies Chama**. Shared shortcode needs composite BillRef (e.g. `CHAMA_CODE-MEMBER_NO`).

---

## Recommended product rule (align with guide + code)

1. **Canonical account number** = `membership_number` within each Chama (already unique).
2. **Display format** (optional): `UM{number:03d}` on UI/PDF, but **M-Pesa Account field = digits only** (or teach parser to accept `UM001` → `1`).
3. **Never reuse** a membership number after exit (keep unique; mark membership inactive).
4. **On join**: allocate next number; show on profile:  
   *“Paybill {shortcode} · Account {membership_number}”*.
5. **C2B validate/confirm**: keep current lookup; surface BillRef on member profile + payments help screen.
6. **If one Paybill for the whole platform**: change OQ-021 to composite BillRef (`{chama_code}{membership_number}`) and resolve both; that is a deliberate design change.
7. **Account updates**: do not change number on rename; only status/roles. Number is the stable payment key.

---

## Concrete improvements for the agent

| Priority | Work |
|----------|------|
| **P0** | Expose `membership_number` + Paybill shortcode on membership/me/chama payment instructions API + FE |
| **P0** | Document for members: Account = membership number (digits) |
| **P1** | Accept optional prefixed BillRef (`UM001` / `001`) → normalize to int |
| **P1** | STK `AccountReference` = same membership number for consistency |
| **P2** | C2B purpose codes / BillRef suffix for fine vs contribution vs loan (or separate shortcodes) |
| **P2** | Only if needed: multi-Chama shared shortcode + composite BillRef |

---

## Bottom line

- **`docs/Practical.md`** states the real-world rule: **unique member number = Paybill account number**.
- **ChamaCore already implements that** for C2B via `membership_number` + OQ-021.
- The payment problem is usually **not “missing identity in the model”** — it is **making that number the official, visible Account number**, enforcing digit BillRef, and deciding **one Paybill per Chama** (current) vs **shared Paybill** (needs composite refs).

**Do this next:** treat `membership_number` as the permanent account number per Chama, show it everywhere members pay, and keep C2B matching as-is unless you need shared shortcodes or payment-type codes.
