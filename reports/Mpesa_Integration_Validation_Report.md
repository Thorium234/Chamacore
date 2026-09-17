# ARCHITECTURAL VALIDATION REPORT: MPESA API INTEGRATION FOR CHAMA APPLICATION

## 1. Executive Summary
This validation report provides a structural and operational blueprint for the integration of Safaricom M-Pesa APIs into the proposed Chama Application. To achieve optimal user experience and resilient financial auditing, the engineering team must concurrently deploy two distinct M-Pesa primitives within a **FastAPI** framework: **M-Pesa Express (STK Push)** and **Customer-to-Business (C2B) API**.

This document outlines the operational credentials required from the [Safaricom Developer Portal](https://developer.safaricom.co.ke/) and defines the behavioral logic the engineer must implement within FastAPI endpoints without introducing direct code blocks.

---

## 2. Safaricom Developer Portal Requirements
Before implementing any backend infrastructure, the engineer must register an account on the Safaricom Developer Portal, create a sandbox/production application, and obtain or configure the following components:

### A. Authentication & Application Credentials
*   **Consumer Key:** A unique public identifier for the application used to request short-lived OAuth tokens.
*   **Consumer Secret:** A private secret key used alongside the Consumer Key to authenticate backend-to-M-Pesa API calls.

### B. M-Pesa Express (STK Push) Specifics
*   **Business Short Code:** The Paybill number or Till number assigned to the Chama.
*   **Passkey:** A unique string provided in the developer portal used to generate the password for secure STK Push encryption.
*   **Callback URL:** A publicly accessible HTTPS URL exposed by the FastAPI app where Safaricom will send asynchronous transaction receipts.

### C. C2B API Specifics
*   **Validation URL:** A publicly accessible HTTPS URL exposed by the FastAPI app. Safaricom triggers this endpoint *before* processing a manual payment, allowing the app to accept or reject the payment.
*   **Confirmation URL:** A publicly accessible HTTPS URL exposed by the FastAPI app. Safaricom triggers this endpoint *after* a manual payment succeeds, notifying the app to update internal state.
*   **C2B Register URL Activation:** An initial configurations process that must be executed programmatically or via the portal to bind the Validation and Confirmation URLs to the shortcode.

---

## 3. FastAPI Endpoint Architecture & Validation Logic

The backend engineer must design an architecture utilizing asynchronous routes to process incoming payloads from Safaricom.

```
                  ┌─────────────────────────────────────────┐
                  │        Safaricom M-Pesa Gateway         │
                  └────┬─────────────────┬──────────────┬───┘
                       │                 │              │
       [STK Push Callback]     [C2B Validation]   [C2B Confirmation]
                       │                 │              │
                       ▼                 ▼              ▼
           ┌────────────────────────────────────────────────┐
           │              FastAPI Application               │
           └────────────────────────────────────────────────┘
```

### 3.1 M-Pesa Express (STK Push) Functional Flow
1.  **Initiation Endpoint (`POST /api/v1/payments/stk-push`):**
    *   **Action:** Exposed to the client-side Chama mobile/web app. It requests an access token using the Consumer Key and Consumer Secret via Safaricom's OAuth endpoint, compiles the transaction parameters, hashes the password using the Passkey and timestamp, and triggers the Safaricom gateway.
    *   **Response:** Returns a synchronous confirmation to the frontend indicating whether Safaricom successfully pushed the STK prompt to the user's handset.
2.  **Callback Endpoint (`POST /api/v1/payments/stk-callback`):**
    *   **Action:** A public HTTPS route that listens for Safaricom's asynchronous transaction results.
    *   **Internal Validation:** Must parse the JSON structure to check the `ResultCode`. If `ResultCode` is `0`, the payment was successful. The engineer must extract the `MpesaReceiptNumber`, `Amount`, `PhoneNumber`, and `TransactionDate`.
    *   **Ledger Reconciliation:** Update the Chama's specific member contribution record as settled.

### 3.2 C2B API Functional Flow
1.  **Validation Endpoint (`POST /api/v1/payments/c2b-validation`):**
    *   **Action:** Invoked by Safaricom when a member manually pays via Paybill (e.g., M-Pesa Sim Toolkit or M-Pesa App).
    *   **Internal Validation:** The engineer must extract the input metadata, specifically the account number (e.g., `BillRefNumber`). The backend must check the database to confirm if the account number corresponds to a valid, active Chama member or a valid target fund.
    *   **Business Logic Outcome:** If valid, return a JSON response containing `{"ResultCode": 0, "ResultDesc": "Accepted"}`. If invalid or untraceable, return `{"ResultCode": 1, "ResultDesc": "Rejected"}` to prevent unidentifiable money from being locked in the Paybill account.
2.  **Confirmation Endpoint (`POST /api/v1/payments/c2b-confirmation`):**
    *   **Action:** Invoked by Safaricom only if the validation passed and money was successfully moved.
    *   **Internal Validation:** The engineer must log this record to a immutable ledger table. Unlike the validation stage, this route cannot reject the payment; it must return a success response to Safaricom acknowledgment.
    *   **Ledger Reconciliation:** Credit the identified member's Chama savings balance.

---

## 4. Engineering Implementation Checklist

To ensure robust deployment, the engineer must fulfill the following operational constraints:

*   **Implement ID Pydantic Schemas:** Map Safaricom's multi-layered nested JSON objects (`Body -> stkCallback -> CallbackMetadata -> Item`) to strict Pydantic structures for automatic input filtering and error handling.
*   **Idempotency and De-duplication:** Ensure that both the STK Callback and C2B Confirmation endpoints verify the `MpesaReceiptNumber` against existing database transactions before modifying financial figures to prevent duplicate credit processing.
*   **Secure Routing Exposure:** Ensure FastAPI endpoints mapped to validation, confirmation, and callback URLs are fully protected by TLS/HTTPS. Utilize IP white-listing or security token verification if required, but maintain open capability to receive Safaricom's gateway blocks.
*   **Asynchronous Processing Flow:** Utilize FastAPI's `BackgroundTasks` feature to immediately acknowledge Safaricom's webhooks with a success response before running heavy internal database writes or triggering push notifications to the user. This avoids timeout thresholds set by Safaricom's servers.

---
**Status:** Approved for Backend Development Integration  
**Date:** September 17, 2026
