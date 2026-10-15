# Permission matrix

Defined in `backend/app/core/permissions.py` and enforced on the server for every endpoint. Roles are **not
hierarchical**: an admin does not inherit partner approval, a partner does not inherit user administration.
Deal-scoped permissions also require **membership** of that deal; non-members receive `404` (so a deal's existence is
not revealed) and the attempt is audited.

| Permission | Analyst | Partner | Admin | Deal-scoped |
|---|:-:|:-:|:-:|:-:|
| Create a deal (`deal:create`) | ✓ | ✓ | | |
| Read deal, documents, findings, financials (`deal:read`) | ✓ | ✓ | | ✓ |
| List all deals — name, classification, status only (`deal:list_all_metadata`) | | | ✓ | |
| Add members to a deal (`deal:manage_members`) | | ✓ (own deals) | ✓ | |
| Upload documents (`document:upload`) | ✓ | ✓ | | ✓ |
| Delete documents (`document:delete`) | | ✓ | | ✓ |
| Start an analysis run (`run:start`) | ✓ | ✓ | | ✓ |
| Approve / reject a run (`run:review`) | | ✓ | | ✓ |
| Read the approved memo (`report:read`) | ✓ | ✓ | | ✓ |
| Ask questions of the documents (`ask`) | ✓ | ✓ | | ✓ |
| Refresh external sources (`source:refresh`) | | ✓ | | ✓ |
| Manage users (`user:manage`) | | | ✓ | |
| Read and verify the audit log (`audit:read`) | | | ✓ | |
| Turn own two-factor authentication on/off; change own password (any signed-in user) | ✓ | ✓ | ✓ | |
| Issue a password-reset link, reset 2FA, unlock a user — never for themselves (`user:manage`) | | | ✓ | |

## Approval governance

* **Segregation of duties:** the person who started a run cannot review it, even if they are a partner.
* A run can be reviewed only while `awaiting_review`, only once, and only if the deal's inputs (documents +
  financial facts + methodology) still match the run's `inputs_hash`. Otherwise a new run is required.
* Runs where any agent failed are `incomplete` and cannot be approved.
* Verified real-data deals do not accept manual uploads or deletions; their data changes only through an audited
  source refresh.
* On approval the memo is rendered from the persisted findings and stored as an immutable `ReportVersion`
  (sha256 of content and of the findings). Database triggers reject `UPDATE`/`DELETE` on approved reports.
  Later changes to a deal's data never alter an approved memo; they lead to a new run and a new version.

## Audit trail

Every login (success, failure, rate-limited, locked), logout, permission denial, deal access denial, deal creation,
membership change, upload, deletion, source refresh, run start, approval/rejection, report download, user change
and audit verification is written to `audit_log` with user, action, resource, outcome, detail, IP and UTC time.
Rows are hash-chained (`hash = sha256(prev_hash + entry)`), and database triggers block `UPDATE`/`DELETE`.
`GET /api/v1/admin/audit/verify` or `python scripts/manage.py verify-audit` recomputes the chain. Secrets (passwords,
tokens) are scrubbed from audit details.
