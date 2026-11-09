Adds the legal documents of the contracts:

- **Document templates** (Configuration > Contracts > Contract Document
  Templates): a body with placeholders (QWeb, the document is `object`:
  `object.partner_id`, `object.company_id`, `object.contract_id`,
  `object.contract_line_ids`, `object.document_effective_date`,
  `object.parent_id`...), an optional title and language expression, an
  ordered list of **reusable clauses** and optional **annexes** printed in
  the same PDF. Each template has a **type**: *Contract* (main document),
  *Separate document* (non-disclosure agreement, data processing
  agreement..., signed on its own) or *Addendum*.
- **Several documents per contract** (`contract.document`): a contract
  template lists the documents to generate (e.g. service contract + NDA +
  data processing agreement), copied to the contract, where they can be
  changed. *Generate documents* creates the missing ones and renders the
  draft ones in the language of the customer.
- Each document is **frozen once issued**: later changes on the template
  or clauses do not alter it, and it can neither be regenerated nor
  edited. Changes are made with an **addendum** (*New addendum* on the
  document), numbered `<contract>/A1`, A2..., linked to the document it
  amends. Separate documents are numbered `<contract>/D1`, D2...
- A document may also belong to a **partner without contract** (e.g. an
  NDA signed before any contract), numbered `DOC/<year>/nnn`; the partner
  form shows its contract documents.
- Each document prints as its own PDF with the economic conditions
  (recurring lines, if any) and a last signature page.
