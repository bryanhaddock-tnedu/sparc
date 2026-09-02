# SPARC-6 Work Type Mix Card Labels Retrospective

## Summary

Fixed a Dashboard Work Type Mix clarity bug reported from UAT. The stacked bars correctly showed separate Forecast and Actual totals for the selected scope, but the three bucket cards under the bars always displayed Forecast values without saying so. This made the Maintenance bucket card look inconsistent with the Actual total.

## Implementation

- Updated each bucket card to show labeled Forecast and Actual values side by side when actuals are available for the selected period.
- Future-month scopes continue to show only Forecast values.
- The backend aggregation already returned both forecast and actual bucket values, so no calculation change was needed.
- Frontend/interface version bumped to `0.1.111`.

## Validation

For the reported August example, the prior bucket cards showed `953 + 835 + 1530 = 3318`, which matched Forecast Aug, not Actual Aug. After this change, the Maintenance card separately identifies its Forecast and Actual values so the Actual bucket values should reconcile to the Actual Aug total.
