# SPARC-2 Product Assignment Names Retrospective

## Summary

Implemented the SPARC-2 Product Detail assignment-name surface after Florie confirmed no new Operations View is needed. The feature uses existing Product Team assignments and Team Member role labels instead of adding a new assignment model.

Product Detail now displays Product Owner names to Admin, Leadership View Only, and authorized Program Area View Only users. Admin and Leadership View Only also see assigned Developer and QA Engineer names. Program Area View Only does not receive Developer or QA Engineer names from the API.

## Implementation

- Added `GET /api/products/{product_ref}/people`, scoped by the existing Product Program Area visibility rules.
- The response includes only display-name arrays, not Team Member IDs, slugs, bill rates, employment types, teams, or history metadata.
- Product Owner roles are inferred from active Product Team assignments with `Product`, `Product Owner`, or `PO` role labels.
- Developer roles are inferred from active `Dev`, `Developer`, `Sr. Dev`, `Senior Dev`, or `Senior Developer` role labels.
- QA roles are inferred from active `QA`, `QA Engineer`, or `Quality Assurance` role labels.
- Product Detail renders a Product Assignments panel near the top of the page.
- Frontend/interface version bumped to `0.1.110`.

## Notes

Inactive Product Team assignments are intentionally excluded from the display so stale historical relationships do not look like current ownership. If a Product has no assigned Product Owner, the page shows `Not assigned`; that is expected data cleanup rather than a feature failure.

Follow-up on 2026-09-03 made the Product Assignments panel more compact after UAT feedback and recognized the existing `Product` role label as Product Owner.
