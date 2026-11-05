Adds the legal text to contracts:

- **Document templates** (Configuration > Contracts > Contract Document
  Templates): a body with placeholders (QWeb, the contract is `object`),
  an optional title and language expression, and an ordered list of
  **reusable clauses** (confidentiality, data protection, SLA...).
- A contract template can carry a document template, so creating a
  contract from it loads both the recurring lines and the legal text.
- On the contract, *Generate document* renders the text in the language
  of the customer and **freezes** it: later changes on the template or
  clauses do not alter it. Once issued (`document_locked`, e.g. sent for
  signature) it can neither be regenerated nor edited.
- *Print document* produces a PDF with the text, the economic conditions
  (recurring lines) and a last signature page.
