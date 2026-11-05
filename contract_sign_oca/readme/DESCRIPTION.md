Online signature of the contract document with `sign_oca`:

- *Send for signature* renders the contract document PDF, creates a
  `sign.oca.request` linked to the contract, with a signature box for the
  customer and, optionally, for a company representative, placed on the
  last (signature) page, and e-mails the signers.
- When everybody has signed, the contract is marked as signed and the
  final PDF is attached to it. The attachment is taken at the end of the
  transaction, so modules post-processing the signed PDF (e.g. a PAdES
  seal) are included whatever the module order.
- **Signature required** (from the document template, overridable per
  contract): such contracts are not invoiced by the recurring cron until
  they are signed.
- The customer gets a *Sign the contract* button on the contract page of
  the portal.
