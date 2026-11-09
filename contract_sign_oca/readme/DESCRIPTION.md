Online signature of the contract documents with `sign_oca`, **each document
with its own signature**:

- *Send documents for signature* (contract) generates the documents not
  sent yet, freezes them and creates one `sign.oca.request` per document,
  with a signature box for the customer and, optionally, for a company
  representative, on the last (signature) page. Each signer gets **a
  single e-mail** with the links of all its documents. A single document
  (e.g. an addendum, or an NDA without contract) can be sent from its form.
- When everybody has signed a document, it is marked as signed and the
  final PDF is attached to it and posted on the contract (or partner). The
  attachment is taken at the end of the transaction, so modules
  post-processing the signed PDF (e.g. a PAdES seal) are included. A
  signed addendum is recorded as a contract modification.
- **Signature required to invoice** is set on the document template (e.g.
  contract, NDA and data processing agreement yes, addenda no) and can be
  changed per document: the recurring invoicing skips the contract until
  all its required documents (also the ones not generated yet) are signed.
  The contract shows the overall state ("1 of 3").
- The portal contract page lists the documents with a *Sign* button.
