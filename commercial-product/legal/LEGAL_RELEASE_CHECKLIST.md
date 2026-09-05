# BossAI Video Agent Legal Release Checklist

Status: **REVIEW REQUIRED — GA BLOCKED**

The legal generator and release gate are already fail-closed. Do not set `approved=true` until an authorized human/legal reviewer has confirmed every item below.

## Required decisions

1. `legalEntityName` — exact contracting/legal entity name.
2. `registeredAddress` — legal/registered business address used in customer terms.
3. `supportEmail` — customer support email that will remain monitored.
4. `privacyContact` — privacy/data-rights contact channel.
5. `salesTerritories` — countries/regions where this release may be commercially offered.
6. `governingLaw` — governing law for customer terms.
7. `disputeVenue` — court/arbitration venue or agreed dispute forum.
8. `refundPolicy` — customer-facing refund/cancellation rule.
9. `supportHours` — support service hours/timezone.
10. `dataRetentionSummary` — retention/deletion rule for BossAI-account/cloud data.
11. `cloudProcessingRegions` — regions where explicitly invoked cloud processing may occur.
12. `termsEffectiveDate` — effective date of the approved customer terms/privacy package.
13. `approvedBy` — authorized approving person/role.
14. `approvedAt` — approval timestamp.

Optional but recommended before approval:

- `supportPhone` if a phone support channel will be advertised.
- Verify voice/avatar authorization language against the intended customer markets.
- Verify refund language against the actual HQ Commerce billing/refund implementation.
- Verify cloud-processing-region language against the providers actually enabled for the release.

## Approval workflow

1. Copy `legal-config.template.json` to an internal, non-public approval config.
   The template carries a `_guide` block explaining each field; both the preflight and the
   generator ignore it. `LEGAL_CONFIG_WORKSHEET.md` reduces the 14 fields below to 8
   questions and states what each one affects if it is answered wrongly.
2. Fill every required decision above.
3. Keep `approved=false` while the package is still under review.
4. Run:

```text
python legal/legal-release-preflight.py --config <approved-config.json>
```

5. After authorized approval, set `approved=true`, `approvedBy`, and `approvedAt`.
6. Run the preflight again; it must PASS.
7. Generate the exact release bundle with `generate-customer-legal.py`.
8. Re-run `release-gate.py`. The `customer-legal` check must be backed by the generated `legal-release-manifest.json`; never turn the product manifest green manually.

## Generated GA legal files

The approved generator produces:

- `CUSTOMER_TERMS.md`
- `PRIVACY_NOTICE.md`
- `VOICE_AVATAR_AUTHORIZATION.md`
- `SUPPORT_AND_INSTALLATION.md`
- `legal-release-manifest.json`

These files are release artifacts only after the approved legal config passes machine preflight.
